"""E2E tests: TestUC011_CreateChatBranch."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_agents, get_strategy


class TestUC011_CreateChatBranch:
    """
    Use Case UC-011: Create Chat Branch

    Test Cases:
    - TC-029: Create Branch And Switch
    - TC-030: Create Branch And Stay
    - TC-031: Create Branch With Custom Name
    - TC-044: Branch Preserves Strategy Type
    - TC-045: Branch Preserves SlidingWindow Configuration
    """

    def test_tc_029_create_branch_and_switch(self):
        """
        TC-029: Create Branch And Switch
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchSwitch\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "\n"  # Accept default name
            "y\n"  # Switch to branch
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Продолжить в новой ветке?" in stdout
        agents = get_agents()
        assert len(agents) == 2
        original = get_agent_by_name("BranchSwitch")
        assert original is not None
        branch = next(a for a in agents if a["id"] != original["id"])
        assert "BranchSwitch" in branch["name"]
        assert "branch" in branch["name"]
        assert branch["conversation_id"] != original["conversation_id"]
        assert get_strategy(branch)["strategy_type"] == "DefaultStrategy"

    def test_tc_030_create_branch_and_stay(self):
        """
        TC-030: Create Branch And Stay
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchStay\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "\n"  # Accept default name
            "n\n"  # Stay in current
            "4\n"  # Exit
        )

        _, _, _ = run_cli_command(test_input)

        assert len(get_agents()) == 2
        original = get_agent_by_name("BranchStay")
        assert original is not None
        branch = next(a for a in get_agents() if a["id"] != original["id"])
        assert "BranchStay" in branch["name"]

    def test_tc_031_create_branch_with_custom_name(self):
        """
        TC-031: Create Branch With Custom Name
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Original\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "My Custom Branch\n"  # Custom name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        _, _, _ = run_cli_command(test_input)

        branch = get_agent_by_name("My Custom Branch")
        assert branch is not None
        assert len(get_agents()) == 2

    def test_tc_044_branch_preserves_strategy_type(self):
        """
        TC-044: Branch Preserves Strategy Type
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchStrategy\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "2\n"  # SummarizationStrategy
            "\n" + "\n"  # Default params
            "/branch\n"  # Create branch
            "\n"  # Accept name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        _, _, _ = run_cli_command(test_input)

        agents = get_agents()
        assert len(agents) == 2
        assert all(
            get_strategy(a)["strategy_type"] == "SummarizationStrategy"
            for a in agents
        )

    def test_tc_045_branch_preserves_sliding_window_configuration(self):
        """
        TC-045: Branch Preserves SlidingWindow Configuration
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchSliding\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "4\n"  # SlidingWindowStrategy
            "15\n"  # window_size=15
            "/branch\n"  # Create branch
            "\n"  # Accept name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        _, _, _ = run_cli_command(test_input)

        agents = get_agents()
        assert len(agents) == 2
        assert all(
            get_strategy(a)["strategy_type"] == "SlidingWindowStrategy"
            and get_strategy(a)["window_size"] == 15
            for a in agents
        )
