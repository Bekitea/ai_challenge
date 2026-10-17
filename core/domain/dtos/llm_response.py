from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.domain.dtos.tool_call import ToolCall

if TYPE_CHECKING:
    from core.domain.dtos.rag_context_chunk import RagContextChunk


@dataclass
class LlmResponse:
    """Результат ответа от LLM."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tool_calls: list[ToolCall] | None = None  # Вызовы инструментов
    # Чанки, использованные как RAG-контекст. ``None`` — RAG не задействован
    # (нет подключённых баз знаний), пустой список — базы есть, но ни один
    # чанк не прошёл порог релевантности.
    rag_sources: list[RagContextChunk] | None = None
