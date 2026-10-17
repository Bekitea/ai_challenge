"""Эндпоинты глобальной памяти о пользователе."""

from __future__ import annotations

from fastapi import APIRouter

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import GlobalMemory

router = APIRouter(tags=["memory"])


@router.get("/memory/global", response_model=GlobalMemory)
def get_global_memory(uc: UseCasesDep):
    """Факты из глобальной памяти о пользователе."""
    return GlobalMemory(facts=uc.view_global_memory.execute())
