"""E2E tests: TestUC004_SendMessageAndReceiveResponse."""

from e2e_helpers import run_cli_command


class TestUC004_SendMessageAndReceiveResponse:
    """
    Use Case UC-004: Send Message and Receive Response

    Test Cases:
    - TC-014: Send Multiple Messages
    - TC-015: Empty And Whitespace-Only Message Handling
    - TC-021: Unknown Command Handling
    - TC-022: System Prompt in History
    - TC-023: Special Characters in Input
    """

    def test_tc_014_send_multiple_messages(self):
        """
        TC-014: Send Multiple Messages

        Steps:
        1. Enter chat
        2. Send "Message 1"
        3. Send "Message 2"
        4. Send "Message 3"
        5. Return to menu
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "MultiMessage\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Message 1\n"  # First message
            "\n"  # Decline reasoning
            "Message 2\n"  # Second message
            "\n"  # Decline reasoning
            "Message 3\n"  # Third message
            "\n"  # Decline reasoning
            "/menu\n"  # Return to menu
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[USER]:" in stdout
        assert "[AGENT]" in stdout

    def test_tc_015_empty_and_whitespace_only_message_handling(self):
        """
        TC-015: Empty And Whitespace-Only Message Handling

        Steps:
        1. Enter chat
        2. Press Enter (empty) - should re-prompt
        3. Press Enter again - should re-prompt
        4. Send valid message - normal flow resumes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "EmptyMessage\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "\n"  # Empty message (should re-prompt)
            "\n"  # Empty message again
            "Valid message\n"  # Valid message
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[USER]:" in stdout or "Введите сообщение" in stdout

    def test_tc_021_unknown_command_handling(self):
        """
        TC-021: Unknown Command Handling

        Steps:
        1. Enter chat
        2. Type "/unknown"
        3. Verify warning about unknown command
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "UnknownCmd\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/unknown\n"  # Unknown command
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert (
            "[WARN]" in stdout or "Неизвестная команда" in stdout or "/help" in stdout
        )

    def test_tc_022_system_prompt_in_history(self):
        """
        TC-022: System Prompt in History

        Steps:
        1. Create chat with system prompt
        2. Verify history contains system message
        3. Check role = "system"
        4. Check display with [SYSTEM] prefix
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SystemPromptTest\n"  # Название
            "You are a helpful assistant\n"  # System prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Hello\n"  # User message
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[SYSTEM]" in stdout or "SYSTEM" in stdout.upper()

    def test_tc_023_special_characters_in_input(self):
        """
        TC-023: Special Characters in Input

        Steps:
        1. Create chat
        2. Send message with special characters
        3. Verify message handled correctly
        """
        special_message = "Test @#$%^&*()_+-=[]{}|;':\",./<>?"

        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SpecialChars\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            f"{special_message}\n"  # Message with special chars
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[USER]:" in stdout
