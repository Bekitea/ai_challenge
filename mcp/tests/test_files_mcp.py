"""Pytest-обёртка над MCP-сервером файлов проекта.

Offline: сервер поднимается как subprocess через MCP stdio-транспорт и
работает с корнем репозитория. Запись проверяется в режиме dry-run и на
временном файле, который удаляется после теста.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

SERVER = str(Path(__file__).resolve().parents[1] / "files_mcp.py")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _text(result) -> str:
    return "\n".join(c.text for c in result.content if c.type == "text")


async def _call(
    tool: str, arguments: dict, env: dict | None = None
) -> tuple[list[str], str]:
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=env)
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = [tool.name for tool in tools.tools]
        result = await session.call_tool(tool, arguments)
        return names, _text(result)


def test_files_mcp_lists_tools():
    """Сервер отдаёт все файловые инструменты."""
    names, _ = asyncio.run(_call("list_files", {"path": "mcp", "pattern": "*.py"}))
    assert "read_file" in names
    assert "search_in_files" in names
    assert "write_file" in names
    assert "replace_in_file" in names


def test_files_mcp_read_and_search():
    """Чтение README и поиск по проекту возвращают содержимое."""
    _, read_text = asyncio.run(_call("read_file", {"path": "README.md"}))
    assert "--- README.md ---" in read_text

    _, search_text = asyncio.run(
        _call("search_in_files", {"query": "MCP", "path": "docs", "mask": "*.md"})
    )
    assert "Найдено совпадений" in search_text or "не найдено" in search_text


def test_files_mcp_env_is_forbidden():
    """Файлы .env читать запрещено."""
    _, text = asyncio.run(_call("read_file", {"path": ".env"}))
    assert "запрещён" in text


def test_files_mcp_write_dry_run_then_apply():
    """write_file по умолчанию показывает diff, а apply=True создаёт файл."""
    name = f".pytest_files_mcp_{uuid.uuid4().hex}.txt"
    try:
        _, preview = asyncio.run(
            _call("write_file", {"path": name, "content": "hello\n"})
        )
        assert "PREVIEW" in preview
        assert not (PROJECT_ROOT / name).exists()

        _, applied = asyncio.run(
            _call("write_file", {"path": name, "content": "hello\n", "apply": True})
        )
        assert "записан" in applied
        assert (PROJECT_ROOT / name).read_text(encoding="utf-8") == "hello\n"
    finally:
        target = PROJECT_ROOT / name
        if target.exists():
            target.unlink()


def test_files_mcp_path_escape_forbidden():
    """Выход за пределы корня проекта запрещён."""
    _, text = asyncio.run(_call("read_file", {"path": "../../etc/passwd"}))
    assert "Ошибка" in text


def test_files_mcp_root_override(tmp_path):
    """PROJECT_FILES_ROOT переопределяет корень рабочего пространства."""
    (tmp_path / "note.txt").write_text("inside workspace\n", encoding="utf-8")
    env = {**os.environ, "PROJECT_FILES_ROOT": str(tmp_path)}

    _, text = asyncio.run(_call("read_file", {"path": "note.txt"}, env=env))
    assert "--- note.txt ---" in text
    assert "inside workspace" in text

    _, applied = asyncio.run(
        _call(
            "write_file",
            {"path": "created.txt", "content": "ok\n", "apply": True},
            env=env,
        )
    )
    assert "записан" in applied
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "ok\n"
