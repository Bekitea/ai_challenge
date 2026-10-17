from __future__ import annotations

from dataclasses import replace

from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class SetRerankerEnabledUseCase:
    """Use case включения/отключения реранкинга для конкретного чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, enabled: bool) -> bool:
        """Обновляет per-chat флаг реранкинга, сохраняя остальные настройки."""
        agent = _require_agent(self.repository, agent_id)
        current = agent.get_settings()
        agent.update_settings(
            replace(current, reranker_enabled=bool(enabled)), self.repository
        )
        return bool(enabled)
