from __future__ import annotations

from typing import Any, Protocol

from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.dtos.llm_response import LlmResponse


class LlmProvider(Protocol):
    """Порт LLM-провайдера, известный домену.

    Конкретные реализации (Yandex Cloud, Ollama, mock) живут в
    инфраструктуре и структурно удовлетворяют этому протоколу.
    """

    provider_name: str

    def list_models(self) -> list[LlmModelInfo]:
        """Возвращает список доступных у провайдера моделей."""
        ...

    def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int = 20,
        top_p: float | None = None,
        top_k: float | None = None,
        response_format: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        model_id: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_retries: int | None = None,
    ) -> LlmResponse:
        """Генерирует ответ от LLM."""
        ...
