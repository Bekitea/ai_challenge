from __future__ import annotations

from typing import Protocol

from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.protocols.llm_provider import LlmProvider


class LlmRegistry(Protocol):
    """Порт реестра именованных LLM-провайдеров."""

    def get(self, name: str) -> LlmProvider | None:
        """Возвращает провайдера по имени или ``None``."""
        ...

    def all(self) -> dict[str, LlmProvider]:
        """Возвращает словарь всех провайдеров."""
        ...

    def list_models(self) -> list[tuple[str, LlmModelInfo]]:
        """Агрегирует модели всех провайдеров."""
        ...
