"""Тесты LLM Gateway: сериализация, проксирование и граничные случаи очереди."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from fastapi.testclient import TestClient

from llm_gateway.queue import InProcessQueue, Job, RedisQueue, Result
from llm_gateway.server import create_app
from llm_gateway.worker import Worker


class RecordingUpstream:
    """Заглушка upstream: считает одновременные вызовы и пишет историю."""

    def __init__(self, delay: float = 0.0, result: Result | None = None) -> None:
        self.delay = delay
        self.result = result or Result(status=200, body={"ok": True})
        self.active = 0
        self.max_active = 0
        self.calls: list[tuple[str, str, Any]] = []
        self._lock = threading.Lock()

    def request(self, method: str, path: str, payload: Any = None) -> Result:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if self.delay:
            time.sleep(self.delay)
        with self._lock:
            self.active -= 1
            self.calls.append((method, path, payload))
        return self.result


def test_worker_serializes_requests() -> None:
    """Гарантия choke point: одновременно в upstream уходит ровно один запрос."""
    queue = InProcessQueue(max_depth=10)
    upstream = RecordingUpstream(delay=0.05)
    worker = Worker(queue, upstream, block_ms=10)
    worker.start()
    try:
        jobs = [
            Job.create("POST", "/v1/chat/completions", {"i": index})
            for index in range(3)
        ]
        for job in jobs:
            queue.enqueue(job)
        results = [queue.wait(job.request_id, timeout=5) for job in jobs]
    finally:
        worker.stop()

    assert all(result.status == 200 for result in results)
    assert upstream.max_active == 1
    assert len(upstream.calls) == 3


class _FakeRedis:
    """Заглушка redis-клиента для проверки вызова XAUTOCLAIM."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload
        self.xautoclaim_kwargs: dict | None = None

    def xautoclaim(self, stream, group, consumer, **kwargs):
        self.xautoclaim_kwargs = kwargs
        fields = {"data": json.dumps(self.payload)} if self.payload else {}
        return ("0-0", [("1-1", fields)], [])


def test_redis_reclaim_uses_start_id() -> None:
    """Регрессия: XAUTOCLAIM принимает start_id, а не start (redis-py 6.x)."""
    fake = _FakeRedis(
        Job.create("POST", "/v1/chat/completions", {"i": 1}).to_dict()
    )
    queue = RedisQueue.__new__(RedisQueue)
    queue._redis = fake
    queue._stream = "llm:jobs"
    queue._group = "gateway"
    queue._consumer = "worker-1"

    jobs = queue.reclaim()

    assert fake.xautoclaim_kwargs is not None
    assert fake.xautoclaim_kwargs["start_id"] == "0-0"
    assert "start" not in fake.xautoclaim_kwargs
    assert len(jobs) == 1
    assert jobs[0].message_id == "1-1"
    assert jobs[0].method == "POST"


def test_worker_survives_reclaim_failure() -> None:
    """Сбой переклэйма не убивает потребитель — задачи всё равно обрабатываются."""
    class _BrokenReclaimQueue(InProcessQueue):
        def reclaim(self) -> list[Job]:
            raise RuntimeError("redis down")

    queue = _BrokenReclaimQueue(max_depth=10)
    upstream = RecordingUpstream()
    worker = Worker(queue, upstream, block_ms=10)
    worker.start()
    try:
        job = Job.create("POST", "/v1/chat/completions", {})
        queue.enqueue(job)
        result = queue.wait(job.request_id, timeout=5)
    finally:
        worker.stop()

    assert result.status == 200
    assert len(upstream.calls) == 1


def test_worker_survives_dequeue_failure() -> None:
    """Временная ошибка чтения очереди не убивает потребитель."""
    class _FlakyDequeueQueue(InProcessQueue):
        def __init__(self, max_depth: int) -> None:
            super().__init__(max_depth)
            self._raised = False

        def dequeue(self, block_ms: int) -> Job | None:
            if not self._raised:
                self._raised = True
                raise RuntimeError("transient redis error")
            return super().dequeue(block_ms)

    queue = _FlakyDequeueQueue(max_depth=10)
    upstream = RecordingUpstream()
    worker = Worker(queue, upstream, block_ms=10)
    worker.start()
    try:
        job = Job.create("POST", "/v1/chat/completions", {})
        queue.enqueue(job)
        result = queue.wait(job.request_id, timeout=5)
    finally:
        worker.stop()

    assert result.status == 200


def test_worker_returns_502_on_upstream_error() -> None:
    """Ошибка upstream не роняет потребитель, а прокидывается как 502."""
    queue = InProcessQueue(max_depth=10)
    upstream = RecordingUpstream(result=Result(status=502, body={"error": "down"}))
    worker = Worker(queue, upstream, block_ms=10)
    worker.start()
    try:
        job = Job.create("POST", "/v1/chat/completions", {})
        queue.enqueue(job)
        result = queue.wait(job.request_id, timeout=5)
    finally:
        worker.stop()
    assert result.status == 502


def test_http_chat_passthrough() -> None:
    """HTTP-слой возвращает ответ upstream как есть."""
    queue = InProcessQueue(max_depth=10)
    upstream = RecordingUpstream(result=Result(status=200, body={"result": "ok"}))
    app = create_app(queue=queue, upstream=upstream)
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "m", "messages": []}
        )
    assert response.status_code == 200
    assert response.json() == {"result": "ok"}
    assert upstream.calls[0][1] == "/v1/chat/completions"


def test_http_embed_passthrough() -> None:
    """Эмбеддинги также проходят через gateway."""
    queue = InProcessQueue(max_depth=10)
    upstream = RecordingUpstream(result=Result(status=200, body={"embeddings": [[]]}))
    app = create_app(queue=queue, upstream=upstream)
    with TestClient(app) as client:
        response = client.post("/api/embed", json={"model": "bge-m3", "input": ["x"]})
    assert response.status_code == 200
    assert upstream.calls[0][1] == "/api/embed"


def test_http_tags_passthrough() -> None:
    """Список моделей проксируется на /api/tags."""
    queue = InProcessQueue(max_depth=10)
    upstream = RecordingUpstream(result=Result(status=200, body={"models": []}))
    app = create_app(queue=queue, upstream=upstream)
    with TestClient(app) as client:
        response = client.get("/api/tags")
    assert response.status_code == 200
    assert upstream.calls[0][0] == "GET"


def test_health_reports_queue_depth() -> None:
    """Health отдаёт состояние очереди."""
    queue = InProcessQueue(max_depth=10)
    app = create_app(queue=queue, upstream=RecordingUpstream(), start_worker=False)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["queue_depth"] == 0


def test_queue_full_returns_503() -> None:
    """Переполнение очереди — 503 (fail fast), без обращения к upstream."""
    queue = InProcessQueue(max_depth=0)
    app = create_app(queue=queue, upstream=RecordingUpstream(), start_worker=False)
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "m", "messages": []}
        )
    assert response.status_code == 503


def test_queue_timeout_returns_504() -> None:
    """Нет ответа за время ожидания — 504."""
    queue = InProcessQueue(max_depth=10)
    app = create_app(
        queue=queue,
        upstream=RecordingUpstream(),
        queue_wait_timeout=0.1,
        start_worker=False,
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions", json={"model": "m", "messages": []}
        )
    assert response.status_code == 504


def test_cancel_unblocks_wait() -> None:
    """Отмена задачи разблокирует ожидающего с кодом 499."""
    queue = InProcessQueue(max_depth=10)
    job = Job.create("POST", "/v1/chat/completions", {})

    def cancel_soon() -> None:
        time.sleep(0.05)
        queue.cancel(job.request_id)

    threading.Thread(target=cancel_soon, daemon=True).start()
    queue.enqueue(job)
    result = queue.wait(job.request_id, timeout=2)
    assert result.status == 499
