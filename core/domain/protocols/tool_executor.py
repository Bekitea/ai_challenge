from __future__ import annotations

from typing import Protocol

from core.domain.dtos.tool_call import ToolCall


class ToolExecutor(Protocol):
    """Порт исполнителя tool-вызовов, запрошенных моделью.

    Домен отвечает за цикл tool calling, но не знает, откуда пришли
    инструменты (MCP и т.п.) — это скрыто за исполнителем в слое приложения.
    """

    def execute(self, call: ToolCall) -> str: ...
