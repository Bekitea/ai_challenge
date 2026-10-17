"""E2E tests: TestUC003_ReturnToActiveChat."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_agents


class TestUC003_ReturnToActiveChat:
    """
    Use Case UC-003: Return to Active Chat

    Test Cases:
    - TC-012: Return to Chat Without Active Chat
    - TC-013: Return to Chat With Active Chat
    """

    def test_tc_012_return_to_chat_without_active_chat(self):
        """
        TC-012: Return to Chat Without Active Chat

        Steps:
        1. Start application
        2. Verify option 5 shows "(нет активного чата)"
        3. Select option 5
        4. Verify warning displayed
        """
        test_input = (
            "5\n"  # Вернуться в чат (no active chat)
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[WARN] Нет активного чата." in stdout
        assert get_agents() == []

    def test_tc_013_return_to_chat_with_active_chat(self):
        """
        TC-013: Return to Chat With Active Chat

        Steps:
        1. Create or select chat
        2. Type "/menu"
        3. Verify option 5 shows "Вернуться в чат: {name}"
        4. Select option 5
        5. Verify chat loop entered with same context
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ActiveChatTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "5\n"  # Вернуться в чат
            "/menu\n"  # Return to menu again
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Вернуться в чат: ActiveChatTest" in stdout
        assert "[OK] Возврат в чат: ActiveChatTest" in stdout
        assert get_agent_by_name("ActiveChatTest") is not None
