"""Pytest-проверки MCP-сервера научной библиотеки.

Сервер не ходит в сеть для этих случаев: проверяются контракт инструментов,
отсутствие контекста чата и восстановление AI_CHAT_AGENT_ID из окружения.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "research_mcp.py")

EXPECTED_TOOLS = {
    "create_library",
    "list_libraries",
    "switch_library",
    "detach_library",
    "delete_library",
    "get_library_info",
    "update_library_profile",
    "search_articles",
    "import_articles",
    "list_articles",
    "get_article",
    "get_library_stats",
    "summarize_articles",
    "search_library",
    "recommend_articles",
    "get_review_context",
    "get_hypothesis_context",
}


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["APPLICATION_MODE"] = "TEST"
    env["AI_CHAT_TEST_DATA_DIR"] = tempfile.mkdtemp(prefix="research-mcp-")
    return env


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _list_tools(env: dict[str, str]) -> list[str]:
    params = StdioServerParameters(
        command=sys.executable, args=[SERVER], env=env
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        return [tool.name for tool in tools.tools]


async def _call_tool(env: dict[str, str], name: str, arguments: dict) -> str:
    params = StdioServerParameters(
        command=sys.executable, args=[SERVER], env=env
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(name, arguments)
        return _text(result)


def test_research_mcp_lists_tools():
    names = asyncio.run(_list_tools(_env()))
    assert EXPECTED_TOOLS.issubset(set(names))


def test_research_mcp_lists_empty_libraries():
    out = asyncio.run(_call_tool(_env(), "list_libraries", {}))
    assert out.strip().startswith("[")


def test_research_mcp_requires_chat_context():
    out = asyncio.run(_call_tool(_env(), "get_library_info", {}))
    assert out.startswith("[ERROR]")
    assert "AI_CHAT_AGENT_ID" in out
