"""Pytest-обёртка над ручным сценарием проверки MCP-сервера OpenAlex.

Инструмент ``search_articles`` ходит во внешний API ``api.openalex.org``,
поэтому тест требует сети.
"""

import asyncio
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "open_alex_mcp.py")


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _list_tools() -> list[str]:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        return [tool.name for tool in tools.tools]


async def _search() -> str:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "search_articles",
            {"keywords": ["screening", "deep learning"], "year": 2023},
        )
        return _text(result)


def test_open_alex_mcp_lists_tools():
    """Сервер поднимается и регистрирует инструмент поиска статей."""
    names = asyncio.run(_list_tools())

    assert "search_articles" in names


def test_open_alex_mcp_search_articles():
    """Инструмент поиска обращается к OpenAlex и возвращает результат (нужна сеть)."""
    text = asyncio.run(_search())

    assert text.startswith("Найдено статей:"), text
    assert "Название:" in text
    assert "DOI:" in text
