from __future__ import annotations

from core.application.dtos.available_mcp_server_dto import AvailableMcpServerDTO
from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ListAvailableMcpUseCase:
    """Use case для получения списка MCP-серверов, ещё не подключённых к чату."""

    def __init__(self, repository: AgentRepository, mcp_gateway: McpGateway):
        self.repository = repository
        self._mcp_gateway = mcp_gateway

    def execute(self, agent_id: int | None) -> list[AvailableMcpServerDTO]:
        """Возвращает не подключённые к чату MCP-серверы реестра (DTO)."""
        agent = _load_agent(self.repository, agent_id)
        connected = set(agent.connected_mcp_servers) if agent is not None else set()
        return [
            server
            for server in self._mcp_gateway.available_servers()
            if server.name not in connected
        ]
