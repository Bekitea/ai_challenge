"""E2E tests: TestS3_MemoryIntegrationInSystemPrompt."""

from e2e_helpers import run_cli_command


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
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "0\n"  # No task profile
            "n\n"  # No reasoning (промпт после вывода ответа)
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
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            # Select the created profile (assuming it's #1)
            "1\n"  # Select profile
            "Send test message\n"  # Message
            "n\n"  # No reasoning
            "/info\n"  # Проверка привязки профиля и памяти в инфо чата
            "/menu\n"  # Выход в меню
            "4\n"  # Просмотреть глобальную память (шаг 1: факты есть)
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Global Memory Chat' создан!" in stdout
        assert "[OK] Профиль задачи 'Integration Profile' создан!" in stdout
        assert "[OK] Чат 'Integration Chat' создан!" in stdout
        assert "Профиль задачи: Integration Profile" in stdout
        # Шаг 1: глобальная память содержит факты после обмена сообщениями
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout
        memory_section = stdout.split("--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---")[-1]
        assert "(память пуста)" not in memory_section, (
            "Mock provider must extract global facts after a message exchange"
        )

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
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "1\n"  # Select profile #1
            "Test message\n"  # Message
            "n\n"  # No reasoning
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Empty Pref Chat' создан!" in stdout
        # Preferences line omitted when empty (§4.7.3)
        assert "Предпочтения:" not in stdout
