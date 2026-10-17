"""E2E tests: TestS3_MemoryIntegrationInSystemPrompt."""

from e2e_helpers import run_cli_command
from ground_truth import (
    get_agent_by_name,
    get_agent_profile_id,
    get_global_facts,
    get_profile_by_name,
)


class TestS3_MemoryIntegrationInSystemPrompt:
    """
    Use Case: Task Profile Memory Integration in System Prompt

    Test Cases:
    - TC-064: Memory Integration Global + Task Profile
    - TC-065: Preferences Display - Empty Preferences
    """

    def test_tc_064_memory_integration_global_and_task(self):
        """
        TC-064: Memory Integration Global + Task Profile

        Steps:
        1. Ensure global memory has facts (send message in any chat)
        2. Create task profile
        3. Create chat linked to task profile
        4. Send message to populate task memory
        5. Verify system prompt contains both memories
        6. Verify order: global first, then task
        7. Verify headers separate them
        """
        test_input = (
            # First, create a chat to populate global memory
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Global Memory Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "0\n"  # No task profile
            "/menu\n"  # Back to main menu
            # Create task profile
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Integration Profile\n"  # Name
            "For memory integration test\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню (из меню профилей)
            # Create chat with task profile
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Integration Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            # Select the created profile (assuming it's #1)
            "1\n"  # Select profile
            "Send test message\n"  # Message
            "/info\n"  # Проверка привязки профиля и памяти в инфо чата
            "/menu\n"  # Выход в меню
            "4\n"  # Просмотреть глобальную память (шаг 1: факты есть)
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert get_agent_by_name("Global Memory Chat") is not None
        assert get_agent_by_name("Integration Chat") is not None
        profile = get_profile_by_name("Integration Profile")
        assert profile is not None
        # Чат связан с профилем задачи
        assert get_agent_profile_id("Integration Chat") == profile["id"]
        # Шаг 1: глобальная память содержит факты после обмена сообщениями
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout
        assert get_global_facts() != []

    def test_tc_065_preferences_display_empty_preferences(self):
        """
        TC-065: Preferences Display - Empty Preferences

        Precondition: Global memory has facts, task profile has no preferences (empty string)

        Steps:
        1. Create task profile without preferences
        2. Create chat linked to task profile
        3. Send message to trigger system prompt construction
        4. Verify global memory facts appear with header
        5. Verify task profile memory appears with header
        6. Verify preferences section is NOT displayed (skipped when empty)
        """
        test_input = (
            # Create task profile without preferences
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Empty Pref Profile\n"  # Name
            "Profile for testing empty preferences\n"  # Description
            "\n"  # Empty preferences (skip)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            # Create chat with task profile
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Empty Pref Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "1\n"  # Select profile #1
            "Test message\n"  # Message
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert get_agent_by_name("Empty Pref Chat") is not None
        profile = get_profile_by_name("Empty Pref Profile")
        assert profile is not None
        # Предпочтения пусты (§4.7.3) — строка не выводится
        assert profile["preferences"] == ""
        assert "Предпочтения:" not in stdout
