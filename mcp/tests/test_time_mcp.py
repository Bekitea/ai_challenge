"""Pytest-обёртка над ручным сценарием проверки MCP-сервера времени.

Offline: сервер поднимается как subprocess через MCP stdio-транспорт, сеть не
нужна.
"""

import asyncio
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "time_mcp.py")


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _run() -> tuple[list[str], str, str]:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        moscow = await session.call_tool(
            "get_current_time", {"timezone": "Europe/Moscow"}
        )
        zones = await session.call_tool(
            "list_available_timezones", {"region": "Europe"}
        )
        return names, _text(moscow), _text(zones)


def test_time_mcp_tools_and_calls():
    """Сервер отдаёт инструменты времени и корректно обрабатывает вызовы."""
    names, moscow_text, zones_text = asyncio.run(_run())

    assert "get_current_time" in names
    assert "list_available_timezones" in names
    assert moscow_text.startswith("Текущее время (Europe/Moscow):")
    assert "Europe/" in zones_text


async def _invalid_timezone() -> str:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "get_current_time", {"timezone": "Mars/Olympus"}
        )
        return _text(result)


def test_time_mcp_invalid_timezone_reports_error():
    """Невалидный часовой пояс возвращает понятную ошибку, а не падение."""
    text = asyncio.run(_invalid_timezone())

    assert text.startswith("Ошибка:")
