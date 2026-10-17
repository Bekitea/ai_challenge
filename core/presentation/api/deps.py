"""FastAPI-зависимости REST API-слоя."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from core.application.use_cases import UseCasesBundle


def get_use_cases(request: Request) -> UseCasesBundle:
    """Возвращает набор use cases, созданный при старте приложения."""
    return request.app.state.use_cases


# Готовая аннотация зависимости: ``uc: UseCasesDep``.
UseCasesDep = Annotated[UseCasesBundle, Depends(get_use_cases)]
