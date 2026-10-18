"""Pytest-обёртка над MCP-сервером git.

Offline: сервер поднимается как subprocess через MCP stdio-транспорт и читает
git-репозиторий проекта.
"""

import asyncio
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "git_mcp.py")


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _run() -> tuple[list[str], str, str, str]:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=None)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        branch = await session.call_tool("get_current_branch", {})
        status = await session.call_tool("get_status", {})
        changed = await session.call_tool("list_changed_files", {})
        return names, _text(branch), _text(status), _text(changed)


def test_git_mcp_tools_and_calls():
    """Сервер отдаёт git-инструменты и корректно отвечает."""
    names, branch_text, status_text, changed_text = asyncio.run(_run())

    assert "get_current_branch" in names
    assert "get_status" in names
    assert "list_changed_files" in names
    assert "get_diff" in names
    assert branch_text.startswith("Текущая ветка:")
    assert status_text
    assert changed_text
