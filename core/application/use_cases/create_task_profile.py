from __future__ import annotations

from typing import TYPE_CHECKING

from core.application.dtos.task_profile_info import TaskProfileInfo
from core.application.mappers.task_profile_mapper import (
    _task_profile_to_info,
)

if TYPE_CHECKING:
    from core.application.protocols.mcp_gateway import McpGateway


def normalize_mcp_servers(
    mcp_servers: list[str] | None,
    available_names: set[str] | None = None,
) -> list[str]:
    """Убирает дубликаты и (при наличии реестра) проверяет имена серверов."""
    result: list[str] = []
    for raw in mcp_servers or []:
        name = str(raw).strip()
        if not name or name in result:
            continue
        if available_names is not None and name not in available_names:
            raise ValueError(f"MCP-сервер '{name}' не найден в реестре.")
        result.append(name)
    return result


class CreateTaskProfileUseCase:
    """Use case для создания нового профиля задачи."""

    def __init__(
        self,
        task_profile_repository,
        mcp_gateway: McpGateway | None = None,
    ):
        self.task_profile_repository = task_profile_repository
        self._mcp_gateway = mcp_gateway

    def execute(
        self,
        name: str,
        description: str,
        preferences: str = "",
        invariants: list[str] | None = None,
        mcp_servers: list[str] | None = None,
    ) -> TaskProfileInfo:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.
            preferences: Предпочтения и предпочтения пользователя (опционально).
            invariants: Список правил/ограничений (опционально).
            mcp_servers: MCP-серверы, подключаемые к чатам профиля.

        Returns:
            TaskProfileInfo: Информация о профиле.
        """
        available = None
        if self._mcp_gateway is not None:
            available = {
                server.name for server in self._mcp_gateway.available_servers()
            }
        clean_servers = normalize_mcp_servers(mcp_servers, available)
        profile = self.task_profile_repository.create_profile(
            name,
            description,
            preferences,
            invariants,
            clean_servers,
        )
        return _task_profile_to_info(profile)
