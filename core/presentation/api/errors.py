"""Маппинг доменных исключений use cases в HTTP-ответы REST API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.application.exceptions import (
    ContextWindowExceededError,
    LlmTimeoutError,
    RagError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует обработчики доменных исключений на приложении."""

    @app.exception_handler(ContextWindowExceededError)
    async def _context_window(
        _request: Request, exc: ContextWindowExceededError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(LlmTimeoutError)
    async def _llm_timeout(_request: Request, exc: LlmTimeoutError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(RagError)
    async def _rag_error(_request: Request, exc: RagError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
