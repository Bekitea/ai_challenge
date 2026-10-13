"""Единственный потребитель очереди: гарантирует один запрос к Ollama за раз."""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol

from llm_gateway.queue import Job, LlmQueue, Result

logger = logging.getLogger(__name__)


class Upstream(Protocol):
    """Минимальный интерфейс upstream-клиента (для подмены в тестах)."""

    def request(self, method: str, path: str, payload: object = ...) -> Result: ...


class Worker(threading.Thread):
    """Фоновый поток, последовательно обрабатывающий задачи из очереди."""

    def __init__(self, queue: LlmQueue, upstream: Upstream, block_ms: int = 500) -> None:
        super().__init__(daemon=True, name="llm-gateway-worker")
        self._queue = queue
        self._upstream = upstream
        self._block_ms = block_ms
        self._stop_event = threading.Event()

    def run(self) -> None:
        # Дозабираем задачи, «зависшие» после падения прошлого процесса.
        self._reclaim_pending()

        while not self._stop_event.is_set():
            try:
                job = self._queue.dequeue(self._block_ms)
            # Потребитель не должен умирать от разовой ошибки Redis.
            except Exception:
                logger.exception("Ошибка чтения очереди LLM gateway")
                time.sleep(0.5)
                continue
            if job is None:
                continue
            self._process(job)

    def _reclaim_pending(self) -> None:
        """Переклэймливает зависшие задачи, не роняя потребитель при сбое."""
        try:
            for job in self._queue.reclaim():
                self._process(job)
        except Exception:
            logger.exception("Не удалось переклэймить зависшие задачи LLM gateway")

    def _process(self, job: Job) -> None:
        if self._queue.is_cancelled(job.request_id):
            self._queue.complete(
                job, Result(status=499, body={"error": "cancelled"}, error="cancelled")
            )
            return
        try:
            result = self._upstream.request(job.method, job.path, job.payload)
        except Exception as exc:
            logger.exception("Ошибка upstream для %s %s", job.method, job.path)
            result = Result(status=502, body={"error": str(exc)}, error=str(exc))
        self._queue.complete(job, result)

    def stop(self) -> None:
        """Просит поток завершиться и дожидается его остановки."""
        self._stop_event.set()
        self.join(timeout=5)
