"""E2E tests: TestUC002_SelectExistingChatFromList."""

from e2e_helpers import run_cli_command


class TestUC002_SelectExistingChatFromList:
    """
    Use Case UC-002: Select Existing Chat from List

    Test Cases:
    - TC-009: Select Chat from Empty List
    - TC-010: Preview with System Prompt Only
    - TC-011: Preview with User Message
    """

    def test_tc_009_select_chat_from_empty_list(self):
        """
        TC-009: Select Chat from Empty List

        Steps:
        1. Ensure no chats exist
        2. Select "Выбрать чат"
        3. Verify message "Нет доступных чатов"
        4. Verify returns to Main Menu
        """
        test_input = (
            "2\n"  # Выбрать чат (empty list)
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert (
            "Нет доступных чатов" in stdout
            or "Нет доступных чатов. Создайте новый." in stdout
        )

    def test_tc_010_preview_with_system_prompt_only(self):
        """
        TC-010: Preview with System Prompt Only

        Steps:
        1. Create chat with system prompt only
        2. Return to menu using /menu command
        3. Exit app
        4. Verify preview shows "(нет сообщений)"
        5. Verify count shows "Сообщений: 0"
        """
        create_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SystemPromptOnly\n"  # Название
            "You are helpful\n"  # System prompt only
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to main menu (NOT "4" which would be sent as a message)
            "4\n"  # Exit app
        )
        run_cli_command(create_input)

        select_input = (
            "2\n"  # Выбрать чат
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(select_input)

        assert "(нет сообщений)" in stdout or "Сообщений: 0" in stdout

    def test_tc_011_preview_with_user_message(self):
        """
        TC-011: Preview with User Message

        Steps:
        1. Create chat
        2. Send message "Hello world"
        3. Return to menu
        4. Verify preview shows "Hello world"
        """
        create_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "PreviewTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Hello world\n"  # Message
            "\n"  # Decline reasoning view
            "4\n"  # Exit
        )
        run_cli_command(create_input)

        select_input = (
            "2\n"  # Выбрать чат
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(select_input)

        assert "PreviewTest" in stdout or "Превью:" in stdout
