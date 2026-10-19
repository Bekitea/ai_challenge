from __future__ import annotations

from typing import TYPE_CHECKING

from core.application.dtos.task_profile_detail_dto import TaskProfileDetailDTO
from core.application.mappers.task_profile_mapper import _task_profile_to_detail
from core.application.use_cases.create_task_profile import normalize_mcp_servers

if TYPE_CHECKING:
    from core.application.protocols.mcp_gateway import McpGateway


class SetTaskProfileMcpServersUseCase:
    """Заменяет список MCP-серверов профиля задачи."""

    def __init__(
        self,
        task_profile_repository,
        mcp_gateway: McpGateway | None = None,
    ):
        self.task_profile_repository = task_profile_repository
        self._mcp_gateway = mcp_gateway

    def execute(
        self, profile_id: str, mcp_servers: list[str]
    ) -> TaskProfileDetailDTO:
        available = None
        if self._mcp_gateway is not None:
            available = {
                server.name for server in self._mcp_gateway.available_servers()
            }
        clean_servers = normalize_mcp_servers(mcp_servers, available)
        profile = self.task_profile_repository.set_mcp_servers(
            profile_id, clean_servers
        )
        if profile is None:
            raise ValueError(f"Профиль задачи '{profile_id}' не найден.")
        return _task_profile_to_detail(profile)
