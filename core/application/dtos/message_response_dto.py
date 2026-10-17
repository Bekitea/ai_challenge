from __future__ import annotations

from dataclasses import dataclass

from core.application.dtos.rag_source_dto import RagSourceDTO


@dataclass
class MessageResponseDTO:
    """Ответ ассистента на сообщение пользователя (DTO)."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    context_window_size: int | None = None
    rag_sources: list[RagSourceDTO] | None = None
