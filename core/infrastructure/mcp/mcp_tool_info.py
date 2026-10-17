from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class McpToolInfo:
    """Информация об инструменте MCP-сервера."""

    server_name: str
    name: str  # оригинальное имя инструмента на сервере
    prefixed_name: str  # имя инструмента, передаваемое в LLM (server__name)
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_openai_tool(self) -> dict[str, Any]:
        """Преобразует инструмент в OpenAI-compatible описание tool."""
        schema = self.input_schema if isinstance(self.input_schema, dict) else {}
        return {
            "type": "function",
            "function": {
                "name": self.prefixed_name,
                "description": self.description or "",
                "parameters": schema
                if schema
                else {"type": "object", "properties": {}},
            },
        }


def strip_prefix(prefixed_name: str) -> tuple[str, str]:
    """Разбивает 'server__tool' на ('server', 'tool').

    Если разделителя нет — возвращает ('', prefixed_name).
    Разделитель '__' может встречаться в имени инструмента, поэтому
    разбиваем по первому вхождению.
    """
    if "__" in prefixed_name:
        server, tool = prefixed_name.split("__", 1)
        return server, tool
    return "", prefixed_name
