"""E2E tests: TestUC010_ViewChatInfoAndTokenStatistics."""

from e2e_helpers import run_cli_command


class TestUC010_ViewChatInfoAndTokenStatistics:
    """
    Use Case UC-010: View Chat Information and Token Statistics

    Test Cases:
    - TC-028: View Chat Info With Token Statistics
    - TC-043: View Info For Different Strategies
    """

    def test_tc_028_view_chat_info_with_token_statistics(self):
        """
        TC-028: View Chat Info With Token Statistics
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "InfoTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout or "ИНФОРМАЦИЯ" in stdout

    def test_tc_043_view_info_for_different_strategies(self):
        """
        TC-043: View Info For Different Strategies
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "DefaultInfo\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Стратегия:" in stdout or "DefaultStrategy" in stdout
