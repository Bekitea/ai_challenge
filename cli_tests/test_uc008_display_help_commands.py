"""E2E tests: TestUC008_DisplayHelpCommands."""

from e2e_helpers import run_cli_command


class TestUC008_DisplayHelpCommands:
    """
    Use Case UC-008: Display Help Commands

    Test Cases:
    - TC-121: Help Command
    """

    def test_tc_121_help_command(self):
        """
        TC-121: Help Command

        Steps:
        1. Enter chat
        2. Type "/help"
        3. Verify command list displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "HelpTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/help\n"  # Show help
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "/menu" in stdout
        assert "/stop" in stdout
        assert "/settings" in stdout
        assert "/summary" in stdout
        assert "/info" in stdout
        assert "/branch" in stdout
        assert "/help" in stdout
