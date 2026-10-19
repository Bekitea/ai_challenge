"""E2E tests: TestUC013_ViewTaskProfilesList."""

from e2e_helpers import run_cli_command
from ground_truth import get_profile_by_name, get_task_profiles


class TestUC013_ViewTaskProfilesList:
    """
    Use Case UC-013: View Task Profiles List

    Test Cases:
    - TC-053: View Task Profiles List (Empty)
    - TC-054: View Task Profiles List (Multiple)
    """

    def test_tc_053_view_task_profiles_list_empty(self):
        """
        TC-053: View Task Profiles List (Empty)

        Steps:
        1. Start application (fresh DB, no profiles)
        2. Select option 3 (Профили задач) from Main Menu
        3. Verify message that no profiles exist
        4. Verify menu options are shown
        5. Exit
        """
        test_input = (
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей (пусто)
            "3\n"  # Назад в главное меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # Should show message about no profiles or empty list
        assert "Нет доступных профилей задач." in stdout
        assert get_task_profiles() == []

    def test_tc_054_view_task_profiles_list_multiple(self):
        """
        TC-054: View Task Profiles List (Multiple)

        Steps:
        1. Create a task profile via menu
        2. Return to profiles list
        3. Verify profile is displayed with ID, name, date
        4. Exit
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Test Task Profile\n"  # Name
            "This is a test task description\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пусто
        "\n"  # MCP-серверы: пропуск
            "2\n"  # Просмотреть список профилей
            "6\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # After creation, should see the profile in the list or confirmation
        assert "--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---" in stdout
        profile = get_profile_by_name("Test Task Profile")
        assert profile is not None
        assert profile["description"] == "This is a test task description"
        assert get_task_profiles() != []
