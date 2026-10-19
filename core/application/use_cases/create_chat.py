from __future__ import annotations

from typing import TYPE_CHECKING

from core.application.dtos.chat_dto import ChatDTO
from core.application.dtos.settings_dto import SettingsDTO
from core.application.dtos.strategy_selection import StrategySelection
from core.application.mappers.chat_mapper import _agent_to_chat_dto
from core.application.mappers.settings_mapper import (
    _settings_to_agent_settings,
)
from core.application.use_cases._helpers.strategy_builder import _build_strategy
from core.domain.entities.agent_phase import AgentPhase
from core.domain.protocols.agent_repository import AgentRepository

if TYPE_CHECKING:
    from core.application.use_cases.connect_mcp import ConnectMcpUseCase


class CreateChatUseCase:
    """Use case для создания нового чата."""

    def __init__(
        self,
        repository: AgentRepository,
        task_profile_repository=None,
        connect_mcp: ConnectMcpUseCase | None = None,
    ):
        self.repository = repository
        self.task_profile_repository = task_profile_repository
        self._connect_mcp = connect_mcp

    def execute(
        self,
        name: str,
        system_prompt: str | None,
        settings: SettingsDTO,
        strategy_selection: StrategySelection,
        task_profile_id: str | None = None,
        initial_phase: str | None = None,
    ) -> ChatDTO:
        """
        Создаёт новый чат с указанными настройками.

        Args:
            name: Название чата. Пустая строка — имя генерируется автоматически
                («Чат N» по текущему количеству чатов).
            system_prompt: Системный промпт (опционально).
            settings: Настройки агента (DTO).
            strategy_selection: Выбор стратегии управления контекстным окном.
            task_profile_id: UUID профиля задачи (опционально).
            initial_phase: Стартовая фаза агента (``plan``/``execute``/...).
                По умолчанию PLAN.

        Returns:
            ChatDTO: Созданный чат.

        Raises:
            ValueError: Если указан несуществующий профиль задачи.
        """
        # Проверка существования профиля задачи, если он указан
        if task_profile_id is not None and self.task_profile_repository is not None:
            profile = self.task_profile_repository.get_profile_by_id(task_profile_id)
            if profile is None:
                raise ValueError(f"Профиль задачи с ID {task_profile_id} не найден")

        if not name:
            name = f"Чат {len(self.repository.get_all_previews()) + 1}"

        agent = self.repository.create_agent(
            name=name,
            initial_settings=_settings_to_agent_settings(settings),
            system_prompt=system_prompt,
            strategy=_build_strategy(strategy_selection),
            task_profile_id=task_profile_id,
            initial_phase=AgentPhase(initial_phase) if initial_phase else None,
        )

        # Инструменты профиля задачи подключаются к чату сразу при создании.
        mcp_messages: list[str] = []
        if (
            self._connect_mcp is not None
            and agent.agent_id is not None
            and task_profile_id is not None
            and self.task_profile_repository is not None
        ):
            profile = self.task_profile_repository.get_profile_by_id(task_profile_id)
            if profile is not None:
                for server_name in profile.mcp_servers:
                    try:
                        success, message = self._connect_mcp.execute(
                            agent.agent_id, server_name
                        )
                    except Exception as exc:  # noqa: BLE001
                        mcp_messages.append(
                            f"[WARN] Не удалось подключить MCP "
                            f"'{server_name}': {exc}"
                        )
                        continue
                    prefix = "[OK]" if success else "[WARN]"
                    mcp_messages.append(f"{prefix} {message}")

        dto = _agent_to_chat_dto(agent)
        dto.mcp_messages = mcp_messages
        return dto
