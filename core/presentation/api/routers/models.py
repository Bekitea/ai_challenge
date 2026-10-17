"""Эндпоинты доступных моделей и провайдеров."""

from __future__ import annotations

from fastapi import APIRouter

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import AvailableModel

router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[AvailableModel])
def list_models(uc: UseCasesDep):
    """Возвращает список доступных моделей всех провайдеров."""
    return uc.list_models.execute()
