from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LLM_REQUEST_TIMEOUT


@dataclass
class AgentSettings:
    """Настройки агента для взаимодействия с LLM."""

    model_id: str | None = None
    provider: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None
    reranker_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения."""
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "provider": self.provider,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "reasoning_effort": self.reasoning_effort,
                "context_window_size": self.context_window_size,
                "reranker_enabled": self.reranker_enabled,
            }.items()
            if v is not None
        }

    def to_llm_request_properties(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения.

        Таймаут задаётся явно (``LLM_REQUEST_TIMEOUT``): при включённом LLM
        Gateway запрос может простоять в очереди к Ollama, поэтому стандартный
        короткий таймаут провайдера не подходит.
        """
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "reasoning_effort": self.reasoning_effort,
                "timeout": LLM_REQUEST_TIMEOUT,
            }.items()
            if v is not None
        }
