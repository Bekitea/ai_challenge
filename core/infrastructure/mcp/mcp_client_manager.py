from __future__ import annotations

import json
import threading
from typing import Any

from core.infrastructure.mcp.mcp_connection import McpConnection


class McpClientManager:
    """Хранит живые подключения к MCP-серверам по именам агентов/чатов."""

    def __init__(self):
        self._connections: dict[int, dict[str, McpConnection]] = {}
        self._lock = threading.Lock()

    def get_connections(self, agent_id: int) -> dict[str, McpConnection]:
        """Возвращает словарь подключений агента (name -> McpConnection)."""
        with self._lock:
            return dict(self._connections.get(agent_id, {}))

    def add_connection(self, agent_id: int, connection: McpConnection) -> None:
        """Регистрирует (или заменяет) подключение к серверу для агента."""
        with self._lock:
            self._connections.setdefault(agent_id, {})[connection.name] = connection

    def remove_connection(self, agent_id: int, server_name: str) -> bool:
        """Отключает сервер у агента. Возвращает True, если отключали."""
        with self._lock:
            conns = self._connections.get(agent_id)
            if not conns or server_name not in conns:
                return False
            conn = conns.pop(server_name)
            conn.close()
            return True

    def clear_agent(self, agent_id: int) -> None:
        """Полностью очищает подключения агента (например, при удалении чата)."""
        with self._lock:
            for conn in self._connections.pop(agent_id, {}).values():
                conn.close()

    def shutdown(self) -> None:
        """Закрывает все подключения (вызывается при выходе из приложения)."""
        with self._lock:
            for conns in self._connections.values():
                for conn in conns.values():
                    conn.close()
            self._connections.clear()


MCP_MANAGER = McpClientManager()


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
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
