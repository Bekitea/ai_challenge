"""E2E tests: TestUC030_ProjectFileAssistant.

UC-030: `/files <цель>` — ассистент по файлам проекта (files + git MCP).
"""

import json

from e2e_helpers import (
    _QUICK_CHAT,
    get_test_data_path,
    mock_llm,
    run_cli_command,
)
from ground_truth import get_history_by_name, get_mcp_servers_by_name


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "name": name,
        "arguments": json.dumps(arguments, ensure_ascii=False),
    }


def _prepare_workspace() -> tuple[str, dict[str, str]]:
    """Создаёт изолированное рабочее пространство и возвращает его путь."""
    workspace = get_test_data_path() / "files-workspace"
    files = {
        "src/mcp_gateway.py": "class McpGateway:\n    pass\n",
        "src/executor.py": "from src.mcp_gateway import McpGateway\n",
    }
    for rel_path, content in files.items():
        target = workspace / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return str(workspace), files


def _write_responses(
    changelog: str, *, offset: int = 0
) -> list[dict]:
    """Сценарий: поиск → чтение двух файлов → dry-run diff → apply."""
    return [
        {
            "content": "",
            "tool_calls": [
                _tool_call(
                    f"{offset + 1}",
                    "files__search_in_files",
                    {"query": "McpGateway", "path": ".", "mask": "*.py"},
                )
            ],
        },
        {
            "content": "",
            "tool_calls": [
                _tool_call(
                    f"{offset + 2}", "files__read_file", {"path": "src/mcp_gateway.py"}
                ),
                _tool_call(
                    f"{offset + 3}", "files__read_file", {"path": "src/executor.py"}
                ),
            ],
        },
        {
            "content": "",
            "tool_calls": [
                _tool_call(
                    f"{offset + 4}",
                    "files__write_file",
                    {"path": "CHANGELOG.md", "content": changelog},
                ),
                _tool_call(
                    f"{offset + 5}",
                    "files__write_file",
                    {"path": "CHANGELOG.md", "content": changelog, "apply": True},
                ),
            ],
        },
        {
            "content": "Готово: CHANGELOG.md создан по результатам поиска.",
            "prompt_tokens": 10,
            "completion_tokens": 5,
        },
    ]


class TestUC030_ProjectFileAssistant:
    """TC-163..TC-166: /files как ассистент по файлам проекта (UC-030)."""

    def test_tc_163_files_connects_files_and_git_mcp(self):
        """TC-163: /files <цель> отвечает и подключает files + git MCP."""
        test_input = (
            _QUICK_CHAT
            + "/files найди использования McpGateway\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(
            test_input,
            timeout=120,
            mock=mock_llm(
                responses=[
                    {
                        "content": "Готово: McpGateway используется в проекте.",
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                    }
                ]
            ),
        )

        assert "[AGENT]: Готово" in stdout
        servers = get_mcp_servers_by_name("Чат 1")
        assert "files" in servers
        assert "git" in servers

    def test_tc_164_files_reads_searches_and_writes_with_diff(self):
        """TC-164: ассистент ищет, читает 2 файла, показывает diff и пишет файл."""
        workspace, _ = _prepare_workspace()
        changelog = (
            "# Changelog\n\n"
            "- McpGateway используется в src/mcp_gateway.py и src/executor.py\n"
        )
        test_input = (
            _QUICK_CHAT
            + "/files создай CHANGELOG.md по использованиям McpGateway\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(
            test_input,
            timeout=180,
            env={"PROJECT_FILES_ROOT": workspace},
            mock=mock_llm(responses=_write_responses(changelog)),
        )

        assert "[AGENT]: Готово" in stdout
        # Изменения сохранены.
        target = get_test_data_path() / "files-workspace" / "CHANGELOG.md"
        assert target.read_text(encoding="utf-8") == changelog
        # Ассистент прочитал минимум 2 файла и сформировал preview-diff.
        history = get_history_by_name("Чат 1")
        tool_contents = [msg.content for msg in history if msg.role == "tool"]
        assert any("PREVIEW (dry-run)" in text for text in tool_contents)
        assert any("--- src/mcp_gateway.py ---" in text for text in tool_contents)
        assert any("--- src/executor.py ---" in text for text in tool_contents)

    def test_tc_165_bare_files_shows_hint(self):
        """TC-165: голый /files показывает подсказку и не подключает MCP."""
        test_input = _QUICK_CHAT + "/files\n" + "/menu\n" + "8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Задайте задачу по файлам проекта" in stdout
        assert get_mcp_servers_by_name("Чат 1") == []

    def test_tc_166_result_is_reproducible(self):
        """TC-166: повторный запуск той же задачи оставляет тот же результат."""
        workspace, _ = _prepare_workspace()
        changelog = "# Changelog\n\n- McpGateway\n"
        command = "/files создай CHANGELOG.md по McpGateway\n"
        test_input = _QUICK_CHAT + command + command + "/menu\n" + "8\n"
        responses = _write_responses(changelog) + _write_responses(
            changelog, offset=5
        )

        stdout, _, _ = run_cli_command(
            test_input,
            timeout=240,
            env={"PROJECT_FILES_ROOT": workspace},
            mock=mock_llm(responses=responses),
        )

        assert stdout.count("[AGENT]: Готово") == 2
        target = get_test_data_path() / "files-workspace" / "CHANGELOG.md"
        assert target.read_text(encoding="utf-8") == changelog
