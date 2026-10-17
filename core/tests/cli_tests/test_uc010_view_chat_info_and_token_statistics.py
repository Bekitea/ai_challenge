"""E2E tests: TestUC010_ViewChatInfoAndTokenStatistics."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_strategy


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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        agent = get_agent_by_name("InfoTest")
        assert agent is not None
        assert agent["message_count"] == 0
        assert agent["chat_prompt_tokens"] == 0
        assert agent["chat_completion_tokens"] == 0
        assert get_strategy(agent)["strategy_type"] == "DefaultStrategy"

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Стратегия:" in stdout
        agent = get_agent_by_name("DefaultInfo")
        assert agent is not None
        strategy = get_strategy(agent)
        assert strategy["strategy_type"] == "DefaultStrategy"
        # У DefaultStrategy нет параметров окна
        assert "window_size" not in strategy
