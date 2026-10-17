from __future__ import annotations

from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class ConnectMcpUseCase:
    """Use case для подключения MCP-сервера к чату."""

    def __init__(self, repository: AgentRepository, mcp_gateway: McpGateway):
        self.repository = repository
        self._mcp_gateway = mcp_gateway

    def execute(self, agent_id: int, server_name: str) -> tuple[bool, str]:
        """Подключает MCP-сервер к чату: соединение + сохранение списка серверов."""
        agent = _require_agent(self.repository, agent_id)

        if agent.agent_id is None:
            return False, "Агент ещё не сохранён — подключите MCP позже."

        server_info = self._mcp_gateway.find_server(server_name)
        if server_info is None:
            return False, f"MCP-сервер '{server_name}' не найден в реестре."

        if server_name in agent.connected_mcp_servers:
            return False, f"MCP '{server_info.title}' уже подключен к этому чату."

        connection = self._mcp_gateway.create_connection(server_name)
        tools = connection.connect_and_list_tools()
        if not connection.connected:
            return (
                False,
                (
                    f"Не удалось подключиться к MCP '{server_info.title}': "
                    f"{connection.connect_error or 'сервер не вернул инструменты'}"
                ),
            )

        self._mcp_gateway.add_connection(agent.agent_id, server_name, connection)
        agent.attach_mcp_server(server_name, self.repository)
        tool_names = ", ".join(t.name for t in tools) if tools else "нет"
        return (
            True,
            f"MCP '{server_info.title}' подключен. Доступные инструменты: {tool_names}",
        )
