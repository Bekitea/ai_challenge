"""Pytest-обёртка над MCP-сервером поддержки (CRM-заглушка).

Offline: сервер читает локальный JSON-файл из ``mcp/data/``.
"""

import asyncio
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "support_mcp.py")


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _run() -> tuple[list[str], str, str, str, str]:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        ticket = await session.call_tool("get_ticket", {"ticket_id": "T-1001"})
        user = await session.call_tool("find_user", {"identifier": "anna@example.com"})
        tickets = await session.call_tool("list_tickets", {"status": "open"})
        missing = await session.call_tool("get_ticket", {"ticket_id": "NOPE"})
        return (
            names,
            _text(ticket),
            _text(user),
            _text(tickets),
            _text(missing),
        )


def test_support_mcp_tickets_and_users():
    """Сервер отдаёт тикет вместе с пользователем и умеет искать."""
    names, ticket_text, user_text, tickets_text, missing_text = asyncio.run(_run())

    assert "get_ticket" in names
    assert "find_user" in names
    assert "list_tickets" in names
    assert "T-1001" in ticket_text
    assert "Анна Петрова" in ticket_text
    assert "Почему не работает авторизация?" in ticket_text
    assert "anna@example.com" in user_text
    assert "T-1001" in tickets_text
    assert "не найден" in missing_text
