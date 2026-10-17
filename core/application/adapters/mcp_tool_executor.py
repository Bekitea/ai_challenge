from __future__ import annotations

import json
from typing import Any

from core.application.adapters.mcp_tools import reconnect_mcp
from core.application.protocols.mcp_gateway import McpGateway
from core.domain.dtos.tool_call import ToolCall


class McpToolExecutor:
    """Исполнитель tool-вызовов через живые MCP-подключения чата.

    Скрывает от домена инфраструктуру MCP: агент лишь просит исполнить
    ``ToolCall`` и не знает, откуда пришёл инструмент.
    """

    def __init__(self, gateway: McpGateway, agent_id: int):
        self._gateway = gateway
        self._agent_id = agent_id

    def execute(self, call: ToolCall) -> str:
        server_name, tool_name = _strip_prefix(call.name)
        connections = self._gateway.get_connections(self._agent_id)
        conn = connections.get(server_name)
        if conn is None or not conn.connected:
            conn, _error = reconnect_mcp(self._gateway, self._agent_id, server_name)
        if conn is None or not conn.connected:
            return (
                f"[MCP] Ошибка: сервер '{server_name}' не подключен к чату, "
                f"инструмент '{tool_name}' недоступен."
            )
        arguments = _parse_tool_arguments(call.arguments)
        return conn.call_tool(tool_name, arguments)


def _strip_prefix(prefixed_name: str) -> tuple[str, str]:
    """Разбивает 'server__tool' на ('server', 'tool').

    Если разделителя нет — возвращает ('', prefixed_name).
    """
    if "__" in prefixed_name:
        server, tool = prefixed_name.split("__", 1)
        return server, tool
    return "", prefixed_name


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    """Разбирает аргументы tool_call из ответа LLM (JSON-строка или dict)."""
    if raw_arguments is None or raw_arguments == "":
        return {}
    if isinstance(raw_arguments, dict):
        return raw_arguments
    try:
        parsed = json.loads(raw_arguments)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
