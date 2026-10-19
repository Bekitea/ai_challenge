"""Очередь задач к Ollama с единственным потребителем.

Две реализации одного интерфейса:
- ``RedisQueue`` — durable FIFO на Redis Streams (прод): переживает рестарт
  процесса, не подтверждённые задачи переклэймливаются.
- ``InProcessQueue`` — очередь в памяти (dev без Redis и тесты).

Обе версии рассчитаны на ровно одного потребителя: строго один запрос к
Ollama одновременно. Масштабировать потребителей нельзя — иначе нарушается
сериализация.
"""

from __future__ import annotations

import json
import math
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Protocol, runtime_checkable

# Ранги приоритетов (задел под сабагентов). Порядок: высокий -> низкий.
PRIORITY_RANKS = {"high": 0, "normal": 1, "low": 2}


class QueueFullError(Exception):
    """Очередь переполнена (backpressure)."""


class QueueTimeoutError(Exception):
    """Ответ не получен за отведённое время ожидания."""


@dataclass
class Job:
    """Задача на вызов upstream-эндпоинта Ollama."""

    request_id: str
    method: str
    path: str
    payload: Any = None
    priority: str = "normal"
    # Служебные поля потребителя (не сериализуются в Redis).
    message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("message_id", None)
        return data

    @classmethod
    def create(
        cls, method: str, path: str, payload: Any = None, priority: str = "normal"
    ) -> Job:
        return cls(
            request_id=uuid.uuid4().hex,
            method=method,
            path=path,
            payload=payload,
            priority=priority,
        )


@dataclass
class Result:
    """Результат выполнения задачи."""

    status: int
    body: Any
    error: str | None = None

    def to_json(self) -> str:
        return json.dumps(
            {"status": self.status, "body": self.body, "error": self.error}
        )

    @classmethod
    def from_json(cls, raw: str) -> Result:
        data = json.loads(raw)
        return cls(status=data["status"], body=data.get("body"), error=data.get("error"))


@runtime_checkable
class LlmQueue(Protocol):
    """Интерфейс очереди задач (общий для продюсера и потребителя)."""

    def enqueue(self, job: Job) -> None: ...

    def wait(self, request_id: str, timeout: float) -> Result: ...

    def cancel(self, request_id: str) -> None: ...

    def dequeue(self, block_ms: int) -> Job | None: ...

    def complete(self, job: Job, result: Result) -> None: ...

    def is_cancelled(self, request_id: str) -> bool: ...

    def reclaim(self) -> list[Job]: ...

    def depth(self) -> int: ...

    def close(self) -> None: ...


# --------------------------------------------------------------------------- #
# In-process реализация
# --------------------------------------------------------------------------- #
class InProcessQueue:
    """Очередь в памяти. Не durable, только для dev и тестов."""

    def __init__(self, max_depth: int = 200) -> None:
        self._max_depth = max_depth
        self._condition = threading.Condition()
        self._items: list[tuple[int, int, Job]] = []
        self._sequence = 0
        self._replies: dict[str, Result] = {}
        self._cancelled: set[str] = set()

    def enqueue(self, job: Job) -> None:
        with self._condition:
            if len(self._items) >= self._max_depth:
                raise QueueFullError("Очередь LLM gateway переполнена.")
            rank = PRIORITY_RANKS.get(job.priority, PRIORITY_RANKS["normal"])
            self._sequence += 1
            self._items.append((rank, self._sequence, job))
            self._items.sort(key=lambda item: (item[0], item[1]))
            self._condition.notify_all()

    def dequeue(self, block_ms: int) -> Job | None:
        deadline = time.monotonic() + block_ms / 1000
        with self._condition:
            while not self._items:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(remaining)
            return self._items.pop(0)[2]

    def complete(self, job: Job, result: Result) -> None:
        with self._condition:
            self._replies[job.request_id] = result
            self._condition.notify_all()

    def wait(self, request_id: str, timeout: float) -> Result:
        deadline = time.monotonic() + timeout
        with self._condition:
            while request_id not in self._replies:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise QueueTimeoutError(
                        "Превышено время ожидания ответа LLM gateway."
                    )
                self._condition.wait(remaining)
            return self._replies.pop(request_id)

    def cancel(self, request_id: str) -> None:
        with self._condition:
            self._cancelled.add(request_id)
            self._replies[request_id] = Result(
                status=499, body={"error": "cancelled"}, error="cancelled"
            )
            self._condition.notify_all()

    def is_cancelled(self, request_id: str) -> bool:
        with self._condition:
            return request_id in self._cancelled

    def reclaim(self) -> list[Job]:
        return []

    def depth(self) -> int:
        with self._condition:
            return len(self._items)

    def close(self) -> None:
        with self._condition:
            self._condition.notify_all()


# --------------------------------------------------------------------------- #
# Redis-реализация (Redis Streams)
# --------------------------------------------------------------------------- #
class RedisQueue:
    """Durable FIFO-очередь на Redis Streams с одним потребителем."""

    def __init__(
        self,
        redis_url: str,
        max_depth: int = 200,
        stream: str = "llm:jobs",
        group: str = "gateway",
        consumer: str = "worker-1",
        reply_ttl: int = 3600,
    ) -> None:
        import redis

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._max_depth = max_depth
        self._stream = stream
        self._group = group
        self._consumer = consumer
        self._reply_ttl = reply_ttl
        self._ensure_group()

    def _reply_key(self, request_id: str) -> str:
        return f"{self._stream}:reply:{request_id}"

    def _cancel_key(self, request_id: str) -> str:
        return f"{self._stream}:cancel:{request_id}"

    def _ensure_group(self) -> None:
        import redis

        try:
            self._redis.xgroup_create(
                self._stream, self._group, id="0", mkstream=True
            )
        except redis.ResponseError:
            # Группа уже существует — это нормально.
            pass

    def enqueue(self, job: Job) -> None:
        if self._redis.xlen(self._stream) >= self._max_depth:
            raise QueueFullError("Очередь LLM gateway переполнена.")
        self._redis.xadd(
            self._stream,
            {"data": json.dumps(job.to_dict())},
            maxlen=self._max_depth * 2,
            approximate=True,
        )

    def dequeue(self, block_ms: int) -> Job | None:
        response = self._redis.xreadgroup(
            self._group,
            self._consumer,
            {self._stream: ">"},
            count=1,
            block=block_ms,
        )
        if not response:
            return None
        _, messages = response[0]
        message_id, fields = messages[0]
        job = Job(**json.loads(fields["data"]))
        job.message_id = message_id
        return job

    def complete(self, job: Job, result: Result) -> None:
        pipe = self._redis.pipeline()
        reply_key = self._reply_key(job.request_id)
        pipe.rpush(reply_key, result.to_json())
        pipe.expire(reply_key, self._reply_ttl)
        if job.message_id is not None:
            # XACK снимает сообщение с pending, а XDEL удаляет его из потока:
            # иначе XLEN только растёт и `depth()`/backpressure навсегда
            # упирается в MAX_QUEUE_DEPTH (после ~N запросов — вечные 503).
            pipe.xack(self._stream, self._group, job.message_id)
            pipe.xdel(self._stream, job.message_id)
        pipe.execute()

    def wait(self, request_id: str, timeout: float) -> Result:
        item = self._redis.blpop(
            self._reply_key(request_id), timeout=max(1, int(timeout))
        )
        if item is None:
            raise QueueTimeoutError("Превышено время ожидания ответа LLM gateway.")
        _, raw = item
        return Result.from_json(raw)

    def cancel(self, request_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.set(self._cancel_key(request_id), "1", ex=self._reply_ttl)
        reply_key = self._reply_key(request_id)
        pipe.rpush(
            reply_key,
            Result(status=499, body={"error": "cancelled"}, error="cancelled").to_json(),
        )
        pipe.expire(reply_key, self._reply_ttl)
        pipe.execute()

    def is_cancelled(self, request_id: str) -> bool:
        return bool(self._redis.exists(self._cancel_key(request_id)))

    def reclaim(self) -> list[Job]:
        """Возвращает «зависшие» (не подтверждённые) задачи для повторной обработки."""
        import redis

        jobs: list[Job] = []
        try:
            # Ответ XAUTOCLAIM: (next_cursor, messages, deleted_ids); берём [1],
            # чтобы не зависеть от числа элементов в разных версиях Redis.
            claimed = self._redis.xautoclaim(
                self._stream,
                self._group,
                self._consumer,
                min_idle_time=0,
                start_id="0-0",
                count=10,
            )
        except redis.ResponseError:
            return jobs
        messages = claimed[1]
        for message_id, fields in messages:
            job = Job(**json.loads(fields["data"]))
            job.message_id = message_id
            jobs.append(job)
        return jobs

    def depth(self) -> int:
        return math.ceil(self._redis.xlen(self._stream))

    def close(self) -> None:
        self._redis.close()


def build_queue(
    redis_url: str,
    max_depth: int,
    stream: str,
    group: str,
    consumer: str,
    reply_ttl: int,
) -> LlmQueue:
    """Создаёт очередь: Redis при указанном URL, иначе in-process."""
    if redis_url:
        return RedisQueue(
            redis_url=redis_url,
            max_depth=max_depth,
            stream=stream,
            group=group,
            consumer=consumer,
            reply_ttl=reply_ttl,
        )
    return InProcessQueue(max_depth=max_depth)


__all__ = [
    "InProcessQueue",
    "Job",
    "LlmQueue",
    "QueueFullError",
    "QueueTimeoutError",
    "RedisQueue",
    "Result",
    "build_queue",
]
