"""E2E tests: TestUC006_NavigateToMenuFromChat."""

from e2e_helpers import run_cli_command


class TestUC006_NavigateToMenuFromChat:
    """
    Use Case UC-006: Navigate to Menu from Chat

    Test Cases:
    - TC-018: Menu Navigation from Chat
    - TC-122: Concurrent Chat Operations
    """

    def test_tc_018_menu_navigation_from_chat(self):
        """
        TC-018: Menu Navigation from Chat

        Steps:
        1. Enter chat
        2. Type "/menu"
        3. Verify Main Menu displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "MenuNav\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "3\n"  # Return to chat
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "МЕНЮ" in stdout or "AI CHAT CLI" in stdout

    def test_tc_122_concurrent_chat_operations(self):
        """
        TC-122: Concurrent Chat Operations

        Steps:
        1. Create Chat A
        2. Type "/menu"
        3. Create Chat B
        4. Verify both chats exist

        NOTE: All operations performed in single subprocess to ensure
        database state is preserved between operations.
        """
        test_input = (
            "1\n"  # Новый чат - создать Chat A
            "y\n"  # Хотите настроить? (y/n)
            "Chat A\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "1\n"  # Новый чат - создать Chat B
            "y\n"  # Хотите настроить? (y/n)
            "Chat B\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "2\n"  # Выбрать чат - показать список
            "1\n"  # Выбор Chat A -> вход в чат (активный чат становится A)
            "/menu\n"  # Return to menu
            "5\n"  # Вернуться в активный чат (A)
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[OK] Чат 'Chat A' создан!" in stdout
        assert "[OK] Чат 'Chat B' создан!" in stdout
        # Option 2 selected Chat A explicitly
        assert "[OK] Выбран чат: Chat A" in stdout
        # Option 5 returns to the ACTIVE chat, which is A after selecting Chat A via option 2
        assert "[OK] Возврат в чат: Chat A" in stdout
        assert "--- ЧАТ: Chat A [Фаза: PLAN] ---" in stdout
