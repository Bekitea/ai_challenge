from __future__ import annotations

from core.application.dtos.settings_dto import SettingsDTO
from core.application.mappers.settings_mapper import (
    _settings_to_agent_settings,
)
from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class ChangeSettingsUseCase:
    """Use case для изменения настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, new_settings: SettingsDTO) -> None:
        """
        Обновляет настройки чата.

        Args:
            agent_id: ID чата для обновления.
            new_settings: Новые настройки (DTO).
        """
        agent = _require_agent(self.repository, agent_id)
        agent.update_settings(
            _settings_to_agent_settings(new_settings), self.repository
        )
