"""HTTP-слой LLM Gateway (Ollama-совместимый).

Отдаёт наружу эндпоинты, которые ожидает основное приложение, но выполнения
не делает сам: кладёт задачу в очередь и ждёт ответа от единственного
потребителя. Тем самым в Ollama всегда уходит ровно один запрос.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from llm_gateway import config
from llm_gateway.queue import (
    Job,
    LlmQueue,
    QueueFullError,
    QueueTimeoutError,
    build_queue,
)
from llm_gateway.upstream import OllamaUpstream
from llm_gateway.worker import Worker

logger = logging.getLogger(__name__)

# Логические эндпоинты, которые проксируются в Ollama.
CHAT_PATH = "/v1/chat/completions"
EMBED_PATH = "/api/embed"
TAGS_PATH = "/api/tags"
MODELS_PATH = "/v1/models"

_VALID_PRIORITIES = {"high", "normal", "low"}


def _priority(request: Request) -> str:
    value = (request.headers.get("x-llm-priority") or "normal").lower()
    return value if value in _VALID_PRIORITIES else "normal"


def _proxy(
    queue: LlmQueue,
    method: str,
    path: str,
    payload: Any,
    priority: str,
    wait_timeout: float,
) -> JSONResponse:
    """Ставит задачу в очередь и возвращает ответ upstream как есть."""
    job = Job.create(method=method, path=path, payload=payload, priority=priority)
    try:
        queue.enqueue(job)
    except QueueFullError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        result = queue.wait(job.request_id, timeout=wait_timeout)
    except QueueTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="Превышено время ожидания LLM gateway."
        ) from exc

    return JSONResponse(status_code=result.status, content=result.body)


def create_app(
    queue: LlmQueue | None = None,
    upstream: Any | None = None,
    queue_wait_timeout: float | None = None,
    start_worker: bool = True,
) -> FastAPI:
    """Собирает FastAPI-приложение gateway.

    Args:
        queue: Готовая очередь (для тестов). Иначе строится из конфигурации.
        upstream: Готовый upstream-клиент (для тестов). Иначе — ``OllamaUpstream``.
        queue_wait_timeout: Переопределение таймаута ожидания (для тестов).
        start_worker: Запускать ли фонового потребителя (в тестах иногда не нужен).
    """
    wait_timeout = (
        queue_wait_timeout
        if queue_wait_timeout is not None
        else float(config.QUEUE_WAIT_TIMEOUT)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_queue = (
            queue
            if queue is not None
            else build_queue(
                redis_url=config.LLM_GATEWAY_REDIS_URL,
                max_depth=config.MAX_QUEUE_DEPTH,
                stream=config.LLM_GATEWAY_STREAM,
                group=config.LLM_GATEWAY_GROUP,
                consumer=config.LLM_GATEWAY_CONSUMER,
                reply_ttl=config.REPLY_TTL,
            )
        )
        active_upstream = (
            upstream
            if upstream is not None
            else OllamaUpstream(
                base_url=config.OLLAMA_UPSTREAM_URL,
                timeout=config.LLM_UPSTREAM_TIMEOUT,
            )
        )
        worker: Worker | None = None
        if start_worker:
            worker = Worker(active_queue, active_upstream, config.DEQUEUE_BLOCK_MS)
            worker.start()
            logger.info(
                "LLM gateway запущен. Upstream: %s", config.OLLAMA_UPSTREAM_URL
            )

        app.state.queue = active_queue
        app.state.worker = worker
        try:
            yield
        finally:
            if worker is not None:
                worker.stop()
            active_queue.close()

    app = FastAPI(title="LLM Gateway", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        """Проба готовности: доступность очереди и глубина."""
        active: LlmQueue | None = getattr(app.state, "queue", None)
        depth = active.depth() if active is not None else -1
        return {
            "status": "ok",
            "queue_depth": depth,
            "upstream": config.OLLAMA_UPSTREAM_URL,
        }

    @app.post(CHAT_PATH)
    def chat_completions(payload: dict, request: Request) -> JSONResponse:
        """Проксирует чат-запрос через очередь."""
        return _proxy(
            request.app.state.queue,
            "POST",
            CHAT_PATH,
            payload,
            _priority(request),
            wait_timeout,
        )

    @app.post(EMBED_PATH)
    def embed(payload: dict, request: Request) -> JSONResponse:
        """Проксирует запрос эмбеддингов через очередь."""
        return _proxy(
            request.app.state.queue,
            "POST",
            EMBED_PATH,
            payload,
            _priority(request),
            wait_timeout,
        )

    @app.get(TAGS_PATH)
    def tags(request: Request) -> JSONResponse:
        """Проксирует список моделей Ollama через очередь."""
        return _proxy(
            request.app.state.queue, "GET", TAGS_PATH, None, "normal", wait_timeout
        )

    @app.get(MODELS_PATH)
    def models(request: Request) -> JSONResponse:
        """OpenAI-совместимый список моделей (проксируется через очередь)."""
        return _proxy(
            request.app.state.queue, "GET", MODELS_PATH, None, "normal", wait_timeout
        )

    return app
