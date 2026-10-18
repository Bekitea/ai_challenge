"""E2E tests: TestUC029_SupportAssistant.

UC-029: `/support [тикет] <вопрос>` — ассистент поддержки (FAQ RAG +
данные тикета/пользователя через MCP-сервер `support`).
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_mcp_servers_by_name


class TestUC029_SupportAssistant:
    """TC-161..TC-162: /support как ассистент поддержки (UC-029)."""

    def test_tc_161_support_answers_with_ticket_context(self):
        """TC-161: /support с тикетом отвечает и подключает support MCP."""
        test_input = (
            _QUICK_CHAT
            + "/support T-1001 почему не работает авторизация?\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=180)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "не найдена" in stdout or "подключена к чату" in stdout
        # Ground truth: support MCP подключён к чату
        assert "support" in get_mcp_servers_by_name("Чат 1")

    def test_tc_162_bare_support_shows_usage_hint(self):
        """TC-162: голый /support показывает подсказку (alt-flow)."""
        test_input = _QUICK_CHAT + "/support\n" + "/menu\n" + "8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Задайте вопрос поддержки" in stdout
        assert get_mcp_servers_by_name("Чат 1") == []
