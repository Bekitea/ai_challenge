"""E2E tests: TestUC026_EdgeCasesRobustness."""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_agents, get_messages_by_name


class TestUC026_EdgeCasesRobustness:
    """
    Use Case UC-026: Edge Cases and Robustness

    Test Cases:
    - TC-154: EOF During Chat Creation
    - TC-155: Very Long User Message
    """

    def test_tc_154_eof_during_chat_creation(self):
        """
        TC-154: EOF During Chat Creation (UC-026)

        Closing stdin mid-creation must terminate gracefully (no traceback)
        and must not persist a half-created chat.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "Halfway\n"  # Название
            # EOF here (stdin closed before system prompt)
        )

        run_cli_command(test_input)

        # Незавершённое создание не должно персиститься
        assert get_agents() == []

    def test_tc_155_long_message_handling(self):
        """
        TC-155: Very Long User Message (UC-026)

        A very long user message must be accepted, stored intact in history,
        and answered without crash.
        """
        long_message = "X" * 5000

        test_input = (
            _QUICK_CHAT  # Новый чат (быстрое создание: модель + reasoning)
            + long_message
            + "\n/menu\n8\n"  # Выход из чата и приложения
        )

        run_cli_command(test_input)

        messages = get_messages_by_name("Чат 1")
        assert messages[0]["content"] == long_message
        assert messages[1]["role"] == "assistant"
