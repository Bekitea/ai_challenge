from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class McpServerInfo:
    """Описание MCP-сервера, который можно подключить к чату."""

    name: str  # машинное имя (используется в БД и в префиксе инструментов)
    title: str  # отображаемое название
    description: str  # краткое описание для пользователя
    script_path: str  # путь к скрипту сервера относительно корня проекта
    transport: str = "stdio"

    def build_command(self) -> tuple[str, list[str]]:
        """Возвращает (command, args) для запуска сервера через stdio."""
        return sys.executable, [self.script_path]


AVAILABLE_MCP_SERVERS: list[McpServerInfo] = [
    McpServerInfo(
        name="openalex",
        title="OpenAlex",
        description=(
            "Поиск научных статей по ключевым словам через OpenAlex API "
            "(инструмент search_articles)"
        ),
        script_path="mcp/open_alex_mcp.py",
    ),
]


def get_available_servers() -> list[McpServerInfo]:
    """Возвращает список всех доступных MCP-серверов."""
    return list(AVAILABLE_MCP_SERVERS)


def find_server(name: str) -> McpServerInfo | None:
    """Ищет MCP-сервер по машинному имени."""
    for server in AVAILABLE_MCP_SERVERS:
        if server.name == name:
            return server
    return None
