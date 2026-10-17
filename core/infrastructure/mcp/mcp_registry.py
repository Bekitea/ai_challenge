from __future__ import annotations

from core.infrastructure.mcp.mcp_server_info import McpServerInfo

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
    McpServerInfo(
        name="time",
        title="Time",
        description=(
            "Текущие дата и время для любого часового пояса (IANA) "
            "(инструменты get_current_time, list_available_timezones)"
        ),
        script_path="mcp/time_mcp.py",
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
