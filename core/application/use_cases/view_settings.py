from __future__ import annotations

from core.application.dtos.settings_dto import SettingsDTO
from core.application.mappers.settings_mapper import (
    _agent_settings_to_dto,
)
from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ViewSettingsUseCase:
    """Use case для просмотра настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> SettingsDTO | None:
        """Получает настройки чата (DTO)."""
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        return _agent_settings_to_dto(agent.get_settings())
