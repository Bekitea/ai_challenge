from __future__ import annotations

from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class DisconnectMcpUseCase:
    """Use case для отключения MCP-сервера от чата."""

    def __init__(self, repository: AgentRepository, mcp_gateway: McpGateway):
        self.repository = repository
        self._mcp_gateway = mcp_gateway

    def execute(self, agent_id: int, server_name: str) -> tuple[bool, str]:
        """Отключает MCP-сервер от чата."""
        agent = _require_agent(self.repository, agent_id)

        if server_name not in agent.connected_mcp_servers:
            return False, f"MCP '{server_name}' не подключен к этому чату."

        server_info = self._mcp_gateway.find_server(server_name)
        title = server_info.title if server_info else server_name

        if agent.agent_id is not None:
            self._mcp_gateway.remove_connection(agent.agent_id, server_name)
        agent.detach_mcp_server(server_name, self.repository)
        return True, f"MCP '{title}' отключен."
