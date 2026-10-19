from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from core.application.dtos.available_mcp_server_dto import AvailableMcpServerDTO


class McpTool(Protocol):
    """Порт описания инструмента живого MCP-подключения."""

    name: str

    def to_openai_tool(self) -> dict[str, Any]:
        """Возвращает OpenAI-описание инструмента."""
        ...


class McpConnection(Protocol):
    """Порт живого подключения к MCP-серверу."""

    @property
    def connected(self) -> bool: ...

    @property
    def connect_error(self) -> str | None: ...

    @property
    def tools(self) -> list[McpTool]: ...

    def connect_and_list_tools(self) -> list[McpTool]: ...

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        extra_env: dict[str, str] | None = None,
    ) -> str: ...


class McpGateway(Protocol):
    """Порт шлюза к MCP: реестр серверов и живые подключения чата.

    Скрывает от слоя приложения инфраструктуру MCP (менеджер подключений,
    реестр серверов, запуск stdio-процессов).
    """

    def available_servers(self) -> list[AvailableMcpServerDTO]: ...

    def find_server(self, name: str) -> AvailableMcpServerDTO | None: ...

    def create_connection(self, server_name: str) -> McpConnection:
        """Создаёт (но не устанавливает) подключение к серверу реестра."""
        ...

    def get_connections(
        self, agent_id: int
    ) -> Mapping[str, McpConnection]: ...

    def add_connection(
        self, agent_id: int, server_name: str, connection: McpConnection
    ) -> None: ...

    def remove_connection(self, agent_id: int, server_name: str) -> bool: ...
