"""E2E tests: TestUC015_ViewTaskProfileMemory."""

from e2e_helpers import run_cli_command


class TestUC015_ViewTaskProfileMemory:
    """
    Use Case UC-015: View Task Profile Memory

    Test Cases:
    - TC-056: View Task Profile Memory (Empty State)
    - TC-055: View Task Profile Memory (Flow)
    - TC-066: Preferences Display in View Profile - With Preferences
    - TC-067: Preferences Display in View Profile - Empty Preferences
    """

    def test_tc_056_view_task_profile_memory_empty_state(self):
        """
        TC-056: View Task Profile Memory - Empty State

        Steps:
        1. Create a task profile
        2. Select option to view profile memory
        3. Verify profile info displayed (ID, name, date, description)
        4. Verify message that memory is empty
        5. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Memory Test Profile\n"  # Name
            "Test description for memory view\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # TC-056: profile info displayed with empty memory and invariants
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Memory Test Profile" in stdout
        assert "(память пуста)" in stdout
        assert "(инварианты не заданы)" in stdout

    def test_tc_055_view_task_profile_memory_flow(self):
        """
        TC-055: View Task Profile Memory - Flow

        Steps:
        1. Create a task profile
        2. Create a chat linked to this profile
        3. Send messages to populate task memory
        4. View profile memory
        5. Verify profile info displayed
        6. Verify facts displayed as numbered list
        """
        # This test requires creating profile, then chat with that profile,
        # sending messages, then viewing memory
        # Simplified version for now - just verify flow works
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Facts Profile\n"  # Name
            "Profile for testing facts\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Test Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # DefaultStrategy
            "1\n"  # Привязать профиль №1 (Facts Profile)
            "/menu\n"  # Выход из чата в меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'Facts Profile' создан!" in stdout
        assert "[OK] Чат 'Test Chat' создан!" in stdout
        # Profile view reachable after linking a chat to it
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Facts Profile" in stdout

    def test_tc_066_preferences_display_in_view_profile_with_preferences(self):
        """
        TC-066: Preferences Display in View Profile - With Preferences

        Related UC: UC-015 (step 6)

        Precondition: Task profile exists with non-empty preferences text

        Steps:
        1. Create a profile with non-empty preferences, navigate to
           Task Profiles menu and select "View memory" (option 2 -> 1)
        2. Select the profile with preferences (profile №1)
        3. Verify profile details displayed and preferences line shown
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Pref Profile\n"  # Name
            "Profile with preferences\n"  # Description
            "Be concise and formal\n"  # Preferences text (non-empty)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Выбрать профиль с предпочтениями (№1)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # Шаг 2: профиль выбран, детали отображены
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Pref Profile" in stdout
        # Шаг 3: строка `Предпочтения: {preferences_text}` показана
        assert "Предпочтения: Be concise and formal" in stdout

    def test_tc_067_preferences_display_in_view_profile_empty_preferences(self):
        """
        TC-067: Preferences Display in View Profile - Empty Preferences

        Related UC: UC-015 (step 6, §4.7.3)

        Precondition: Task profile exists with empty preferences

        Steps:
        1. Create a profile without preferences, navigate to
           Task Profiles menu and select "View memory" (option 2 -> 1)
        2. Select the profile with empty preferences (profile №1)
        3. Verify profile details displayed and the `Предпочтения:` line
           is omitted entirely (no placeholder like "(не указаны)")
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "NoPref Profile\n"  # Name
            "Profile without preferences\n"  # Description
            "\n"  # Предпочтения (пропуск — пустые предпочтения)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Выбрать профиль с пустыми предпочтениями (№1)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # Шаг 2: профиль выбран, детали отображены
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "NoPref Profile" in stdout
        # Шаг 3 (§4.7.3): при пустых предпочтениях строка полностью опущена
        assert "Предпочтения:" not in stdout
        # ...и не заменяется заглушкой
        assert "(не указаны)" not in stdout
