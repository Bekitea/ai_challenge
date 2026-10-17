from __future__ import annotations

from collections.abc import Mapping

from core.application.dtos.available_mcp_server_dto import AvailableMcpServerDTO
from core.application.protocols.mcp_gateway import McpConnection
from core.infrastructure.mcp.mcp_client_manager import MCP_MANAGER, McpClientManager
from core.infrastructure.mcp.mcp_connection import McpConnection as McpConnectionImpl
from core.infrastructure.mcp.mcp_registry import find_server, get_available_servers


class McpManagerGateway:
    """Адаптер порта ``McpGateway`` поверх менеджера подключений и реестра MCP."""

    def __init__(self, manager: McpClientManager | None = None):
        self._manager = manager if manager is not None else MCP_MANAGER

    def available_servers(self) -> list[AvailableMcpServerDTO]:
        return [
            AvailableMcpServerDTO(
                name=server.name,
                title=server.title,
                description=server.description,
            )
            for server in get_available_servers()
        ]

    def find_server(self, name: str) -> AvailableMcpServerDTO | None:
        server = find_server(name)
        if server is None:
            return None
        return AvailableMcpServerDTO(
            name=server.name,
            title=server.title,
            description=server.description,
        )

    def create_connection(self, server_name: str) -> McpConnection:
        server = find_server(server_name)
        if server is None:
            raise ValueError(f"MCP-сервер '{server_name}' не найден в реестре.")
        return McpConnectionImpl(server)

    def get_connections(self, agent_id: int) -> Mapping[str, McpConnection]:
        return self._manager.get_connections(agent_id)

    def add_connection(
        self, agent_id: int, server_name: str, connection: McpConnection
    ) -> None:
        self._manager.add_connection(agent_id, connection)  # type: ignore[arg-type]

    def remove_connection(self, agent_id: int, server_name: str) -> bool:
        return self._manager.remove_connection(agent_id, server_name)
