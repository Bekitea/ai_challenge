from __future__ import annotations

from dataclasses import dataclass

from core.domain.dtos.rag_context_chunk import RagContextChunk


@dataclass
class RagRetrievalResult:
    """Итог RAG-поиска для диалога агента."""

    chunks: list[RagContextChunk]
    has_knowledge_bases: bool
    below_threshold: bool = False
