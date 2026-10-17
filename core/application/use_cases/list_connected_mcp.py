from __future__ import annotations

from core.application.dtos.mcp_server_status import McpServerStatus
from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ListConnectedMcpUseCase:
    """Use case для получения списка MCP-серверов, подключённых к чату."""

    def __init__(self, repository: AgentRepository, mcp_gateway: McpGateway):
        self.repository = repository
        self._mcp_gateway = mcp_gateway

    def execute(self, agent_id: int | None) -> list[McpServerStatus]:
        """Возвращает статусы всех подключённых к чату MCP-серверов.

        В список попадают и серверы, сохранённые в чате, но недоступные в
        данный момент (живое подключение не установлено или разорвано) —
        они отображаются с connected=False.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is None or agent.agent_id is None:
            return []

        connections = self._mcp_gateway.get_connections(agent.agent_id)
        result: list[McpServerStatus] = []
        for server_name in agent.connected_mcp_servers:
            info = self._mcp_gateway.find_server(server_name)
            conn = connections.get(server_name)
            live = conn is not None and conn.connected
            result.append(
                McpServerStatus(
                    name=server_name,
                    title=info.title if info else server_name,
                    description=info.description
                    if info
                    else "сервер отсутствует в реестре",
                    connected=live,
                    tools=[tool.name for tool in conn.tools] if live else [],
                )
            )
        return result
