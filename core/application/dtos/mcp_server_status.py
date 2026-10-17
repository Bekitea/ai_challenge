from __future__ import annotations

from dataclasses import dataclass


@dataclass
class McpServerStatus:
    """Статус MCP-сервера в контексте чата."""

    name: str  # машинное имя сервера
    title: str  # отображаемое название
    description: str  # описание для пользователя
    connected: bool  # есть ли живое подключение к этому чату
    tools: list[str]  # имена инструментов, доступных через это подключение
