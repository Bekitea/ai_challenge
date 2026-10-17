from __future__ import annotations

from typing import Protocol

from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.dtos.rag_retrieval_result import RagRetrievalResult


class RagRetriever(Protocol):
    """Порт RAG-поиска по базам знаний агента."""

    def retrieve(
        self,
        agent_id: int | None,
        query_text: str,
        max_candidates: int | None = None,
        final_top_k: int | None = None,
        reranker_enabled: bool | None = None,
    ) -> RagRetrievalResult: ...

    def search_knowledge_base(
        self, knowledge_base_id: int, query_text: str, top_k: int | None = None
    ) -> list[RagContextChunk]: ...
