from __future__ import annotations

import logging

from core.domain.dtos.rag_retrieval_result import RagRetrievalResult
from core.domain.entities.agent import Agent
from core.domain.protocols.rag_retriever import RagRetriever as RagService


def _retrieve_rag_context(
    rag_service: RagService | None, agent: Agent, query: str
) -> RagRetrievalResult:
    """Поднимает RAG-контекст, деградируя без него при ошибке провайдера."""
    if rag_service is None or agent.agent_id is None:
        return RagRetrievalResult(chunks=[], has_knowledge_bases=False)
    try:
        return rag_service.retrieve(
            agent.agent_id,
            query,
            reranker_enabled=agent.get_settings().reranker_enabled,
        )
    except Exception:
        logging.getLogger("agent.rag").debug(
            "RAG-поиск недоступен, диалог продолжен без контекста",
            exc_info=True,
        )
        return RagRetrievalResult(chunks=[], has_knowledge_bases=False)
