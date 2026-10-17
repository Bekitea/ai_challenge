"""E2E tests: TestEdgeCases_Robustness."""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_agents, get_messages_by_name


class TestEdgeCases_Robustness:
    """
    Robustness edge cases (EOF during creation, long input).

    Supplement to the spec: graceful termination scenarios.
    """

    def test_tc_edge_eof_during_chat_creation(self):
        """
        Edge case: EOF During Chat Creation

        Closing stdin mid-creation must terminate gracefully (no traceback).
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

    def test_tc_edge_long_message_handling(self):
        """
        Edge case: Long Message Handling

        A very long user message must be accepted without crash.
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
