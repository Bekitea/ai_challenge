from __future__ import annotations

import logging

from core.application.protocols.mcp_gateway import McpConnection, McpGateway

logger = logging.getLogger("agent.mcp")


def reconnect_mcp(
    gateway: McpGateway,
    agent_id: int,
    server_name: str,
) -> tuple[McpConnection | None, str | None]:
    """Переподключает сохранённый MCP-сервер в текущем процессе."""
    server_info = gateway.find_server(server_name)
    if server_info is None:
        return None, f"сервер '{server_name}' не найден в реестре"
    connection = gateway.create_connection(server_name)
    connection.connect_and_list_tools()
    if not connection.connected:
        return None, connection.connect_error or "сервер не вернул инструменты"
    gateway.add_connection(agent_id, server_name, connection)
    return connection, None


def collect_mcp_tools(
    gateway: McpGateway,
    agent_id: int | None,
    server_names: list[str],
    agent_name: str,
) -> list[dict]:
    """Собирает OpenAI-описания инструментов живых MCP-подключений чата.

    Если сохранённый сервер ещё не имеет живого подключения в текущем
    процессе, выполняется попытка переподключения — иначе запрос к LLM ушёл
    бы без tools, и модель ответила бы «у меня нет доступа к инструменту».
    """
    if not server_names or agent_id is None:
        return []
    tools: list[dict] = []
    connections = gateway.get_connections(agent_id)
    for server_name in server_names:
        conn = connections.get(server_name)
        if conn is None or not conn.connected:
            conn, error = reconnect_mcp(gateway, agent_id, server_name)
            if conn is None:
                logger.warning(
                    "MCP-сервер '%s' недоступен для чата #%s (%s): %s",
                    server_name,
                    agent_id,
                    agent_name,
                    error or "неизвестная ошибка",
                )
                continue
        tools.extend(tool.to_openai_tool() for tool in conn.tools)
    return tools
