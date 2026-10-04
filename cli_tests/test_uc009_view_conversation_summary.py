"""E2E tests: TestUC009_ViewConversationSummary."""

from e2e_helpers import run_cli_command


class TestUC009_ViewConversationSummary:
    """
    Use Case UC-009: View Conversation Summary

    Test Cases:
    - TC-026: View Summary With Summarization
    - TC-027: View Summary Without Summarization
    """

    def test_tc_026_view_summary_with_summarization(self):
        """
        TC-026: View Summary With Summarization
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SummaryTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "\n" + "\n"  # Default params
            "/summary\n"  # View summary
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "/summary" in stdout or "Суммаризация" in stdout or "[INFO]" in stdout

    def test_tc_027_view_summary_without_summarization(self):
        """
        TC-027: View Summary Without Summarization
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "NoSummary\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/summary\n"  # View summary
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[INFO]" in stdout or "Суммаризация еще не выполнялась" in stdout
