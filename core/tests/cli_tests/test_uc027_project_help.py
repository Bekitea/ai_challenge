"""E2E tests: TestUC027_ProjectHelp.

UC-027: `/help <вопрос>` — ассистент по проекту (README/docs RAG + git MCP).
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_mcp_servers_by_name


class TestUC027_ProjectHelp:
    """TC-157..TC-158: /help как ассистент по проекту (UC-027)."""

    def test_tc_157_help_asks_about_project(self):
        """TC-157: /help <вопрос> отвечает и подключает git MCP (UC-027 main)."""
        test_input = (
            _QUICK_CHAT
            + "/help как устроен проект?\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=120)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "не найдена" in stdout or "подключена к чату" in stdout
        # Ground truth: git MCP подключён к чату
        assert "git" in get_mcp_servers_by_name("Чат 1")

    def test_tc_158_bare_help_shows_usage_hint(self):
        """TC-158: голый /help показывает подсказку, а не список команд (A1)."""
        test_input = _QUICK_CHAT + "/help\n" + "/menu\n" + "8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Задайте вопрос о проекте" in stdout
        assert "--- ДОСТУПНЫЕ КОМАНДЫ ---" not in stdout
        assert get_mcp_servers_by_name("Чат 1") == []

    def test_tc_158b_commands_lists_commands(self):
        """TC-158b: /commands показывает список команд (UC-008)."""
        test_input = _QUICK_CHAT + "/commands\n" + "/menu\n" + "8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ДОСТУПНЫЕ КОМАНДЫ ---" in stdout
        assert "/commands - показать этот список команд" in stdout
        assert "/help - задать вопрос о проекте" in stdout
