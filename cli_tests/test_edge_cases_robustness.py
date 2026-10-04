"""E2E tests: TestEdgeCases_Robustness."""

from e2e_helpers import run_cli_command


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

    def test_tc_edge_long_message_handling(self):
        """
        Edge case: Long Message Handling

        A very long user message must be accepted without crash.
        """
        long_message = "X" * 5000

        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            + long_message
            + "\n/exit\n6\n"  # Выход из чата и приложения
        )

        run_cli_command(test_input)
