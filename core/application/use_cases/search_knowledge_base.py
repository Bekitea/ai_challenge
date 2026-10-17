from __future__ import annotations

from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.protocols.rag_retriever import RagRetriever as RagService


class SearchKnowledgeBaseUseCase:
    """Use case поиска по одной базе знаний (для меню управления)."""

    def __init__(self, rag_service: RagService):
        self._rag_service = rag_service

    def execute(
        self, knowledge_base_id: int, query_text: str, top_k: int | None = None
    ) -> list[RagContextChunk]:
        return self._rag_service.search_knowledge_base(
            knowledge_base_id, query_text, top_k
        )
