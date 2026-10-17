from __future__ import annotations

from core.application.dtos.message_response_dto import MessageResponseDTO
from core.application.dtos.rag_source_dto import RagSourceDTO
from core.domain.dtos.llm_response import LlmResponse
from core.domain.entities.agent import Agent


def _response_to_dto(response: LlmResponse, agent: Agent) -> MessageResponseDTO:
    """Преобразует ``LlmResponse`` + состояние агента в ``MessageResponseDTO``."""
    counters = agent.token_counters
    rag_sources = None
    if response.rag_sources is not None:
        rag_sources = [
            RagSourceDTO(
                document_name=chunk.document_name,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                relevance=chunk.relevance,
            )
            for chunk in response.rag_sources
        ]
    return MessageResponseDTO(
        content=response.content,
        reasoning=response.reasoning,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_prompt_tokens=counters.total_prompt_tokens,
        total_completion_tokens=counters.total_completion_tokens,
        context_window_size=agent.get_settings().context_window_size,
        rag_sources=rag_sources,
    )
