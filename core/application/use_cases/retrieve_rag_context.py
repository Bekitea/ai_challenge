from __future__ import annotations

from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.protocols.rag_retriever import RagRetriever as RagService


class RetrieveRagContextUseCase:
    """Use case поиска релевантных чанков по базам знаний агента.

    Используется CLI для проверки поиска; диалог агента обращается к
    ``RagService`` напрямую.
    """

    def __init__(self, rag_service: RagService):
        self._rag_service = rag_service

    def execute(
        self,
        agent_id: int | None,
        query_text: str,
        max_candidates: int | None = None,
        final_top_k: int | None = None,
        reranker_enabled: bool | None = None,
    ) -> list[RagContextChunk]:
        return self._rag_service.retrieve(
            agent_id=agent_id,
            query_text=query_text,
            max_candidates=max_candidates,
            final_top_k=final_top_k,
            reranker_enabled=reranker_enabled,
        ).chunks
