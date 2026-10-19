from __future__ import annotations

import config
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
        name="research",
        title="Research Library",
        description=(
            "Научная библиотека диссертации: поиск статей в OpenAlex, импорт "
            "OA-полнотекстов и аннотаций, сводки, систематический обзор, "
            "ответы по базе, рекомендации и гипотезы. У каждого чата своя "
            "библиотека и своя база знаний"
        ),
        script_path="mcp/research_mcp.py",
        call_timeout=config.RESEARCH_MCP_CALL_TIMEOUT,
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
    McpServerInfo(
        name="git",
        title="Git",
        description=(
            "Git-контекст проекта: текущая ветка, статус, изменённые файлы, diff "
            "(инструменты get_current_branch, get_status, list_changed_files, "
            "get_diff)"
        ),
        script_path="mcp/git_mcp.py",
    ),
    McpServerInfo(
        name="files",
        title="Project Files",
        description=(
            "Чтение, поиск и изменение файлов проекта с двухшаговым "
            "подтверждением записи (инструменты list_files, read_file, "
            "search_in_files, write_file, replace_in_file)"
        ),
        script_path="mcp/files_mcp.py",
    ),
    McpServerInfo(
        name="support",
        title="Support CRM",
        description=(
            "Пользователи и тикеты поддержки из локального JSON "
            "(инструменты get_ticket, find_user, list_tickets)"
        ),
        script_path="mcp/support_mcp.py",
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
