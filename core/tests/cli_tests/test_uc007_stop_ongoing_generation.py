"""E2E tests: TestUC007_StopOngoingGeneration."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_messages_by_name


class TestUC007_StopOngoingGeneration:
    """
    Use Case UC-007: Stop Ongoing Generation

    Test Cases:
    - TC-019: Stop Command When Idle
    - TC-034: Stop Command Keeps Active Chat
    - TC-035: Stop Command Preserves Chat State
    """

    def test_tc_019_stop_command_when_idle(self):
        """
        TC-019: Stop Command When Idle

        Steps:
        1. Enter chat
        2. Type "/stop" (no generation)
        3. Verify message about generation status
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "StopIdle\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/stop\n"  # Stop when idle
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # /stop при простое всегда сообщает, что генерация не активна
        assert "Генерация не активна." in stdout
        # Ground truth: idle stop не создаёт сообщений
        agent = get_agent_by_name("StopIdle")
        assert agent is not None
        assert agent["message_count"] == 0
        assert agent["chat_prompt_tokens"] == 0
        assert agent["chat_completion_tokens"] == 0
        assert get_messages_by_name("StopIdle") == []

    def test_tc_034_stop_command_keeps_active_chat(self):
        """
        TC-034: Stop Command Keeps Active Chat

        Note: In mock/test mode, generation is instant.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "StopGen\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "Test message\n"  # Send message
            "/stop\n"  # Try to stop
            "4\n"  # Exit
        )

        run_cli_command(test_input)

        agent = get_agent_by_name("StopGen")
        assert agent is not None
        assert agent["message_count"] == 2
        assert agent["chat_prompt_tokens"] > 0
        assert agent["chat_completion_tokens"] > 0
        assert [m["role"] for m in get_messages_by_name("StopGen")] == [
            "user",
            "assistant",
        ]

    def test_tc_035_stop_command_preserves_chat_state(self):
        """
        TC-035: Stop Command Preserves Chat State

        Steps:
        1. Wait for idle state (no generation active)
        2. Type "/stop"
        3. Verify output "Генерация не активна."
        4. Verify no state changes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "IdleStop\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/stop\n"  # Stop when idle
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Генерация не активна" in stdout
        agent = get_agent_by_name("IdleStop")
        assert agent is not None
        assert agent["message_count"] == 0
        assert agent["chat_prompt_tokens"] == 0
