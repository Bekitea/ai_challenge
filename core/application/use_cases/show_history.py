from __future__ import annotations

from core.application.dtos.history_message_dto import HistoryMessageDTO
from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ShowHistoryUseCase:
    """Use case для показа истории чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> list[HistoryMessageDTO] | None:
        """Получает историю сообщений чата (DTO)."""
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        return [
            HistoryMessageDTO(
                role=message.role,
                content=message.content,
                reasoning=message.reasoning,
                has_tool_calls=bool(message.tool_calls),
                timestamp=message.timestamp,
            )
            for message in agent.get_history()
        ]
