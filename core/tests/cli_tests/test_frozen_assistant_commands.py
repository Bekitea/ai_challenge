"""E2E tests: заморозка ассистентских команд /help, /support, /files.

По умолчанию `ASSISTANT_COMMANDS_ENABLED=false` (BACKLOG.md, раздел 2):
команды скрыты из `/commands` и подсказки, а их вызов сообщает об
отключении и не подключает MCP-серверы.
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_mcp_servers_by_name


class TestFrozenAssistantCommands:
    """Замороженные ассистентские команды не выполняются и не видны."""

    def test_frozen_commands_are_not_listed(self):
        """`/commands` не показывает /help, /support, /files."""
        test_input = _QUICK_CHAT + "/commands\n" + "/menu\n" + "8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ДОСТУПНЫЕ КОМАНДЫ ---" in stdout
        assert "/help - задать вопрос о проекте" not in stdout
        assert "/support - вопрос службе поддержки" not in stdout
        assert "/files - задача по файлам проекта" not in stdout

    def test_frozen_commands_report_disabled_and_do_not_connect_mcp(self):
        """Вызов замороженной команды сообщает об отключении и не подключает MCP."""
        test_input = (
            _QUICK_CHAT
            + "/help как устроен проект?\n"
            + "/support T-1001 привет\n"
            + "/files найди McpGateway\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=60)

        assert "Команда /help временно отключена" in stdout
        assert "Команда /support временно отключена" in stdout
        assert "Команда /files временно отключена" in stdout
        assert get_mcp_servers_by_name("Чат 1") == []
