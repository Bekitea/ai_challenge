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
    # Таймаут одного вызова инструмента. По умолчанию 120 с, но тяжёлым
    # серверам (например, research: скачивание PDF и эмбеддинги) нужно больше.
    call_timeout: float = 120.0

    def build_command(self) -> tuple[str, list[str]]:
        """Возвращает (command, args) для запуска сервера через stdio."""
        return sys.executable, [self.script_path]
