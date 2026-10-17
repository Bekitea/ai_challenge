from __future__ import annotations

from core.application.dtos.chat_dto import ChatDTO
from core.application.dtos.chat_preview_dto import ChatPreviewDTO
from core.application.mappers.chat_mapper import _agent_to_chat_dto
from core.domain.protocols.agent_repository import AgentRepository


class SelectChatUseCase:
    """Use case для выбора существующего чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def get_all_previews(self) -> list[ChatPreviewDTO]:
        """Получает список всех чатов (DTO)."""
        return [
            ChatPreviewDTO(
                agent_id=preview.agent_id,
                name=preview.name,
                last_message_timestamp=preview.last_message_timestamp,
                message_count=preview.message_count,
                last_message_preview=preview.last_message_preview,
            )
            for preview in self.repository.get_all_previews()
        ]

    def get_chat(self, agent_id: int) -> ChatDTO | None:
        """Получает чат (DTO) по числовому ID."""
        agent = self.repository.get_agent(agent_id)
        return _agent_to_chat_dto(agent) if agent is not None else None
