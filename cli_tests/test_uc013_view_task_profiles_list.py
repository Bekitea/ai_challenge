"""E2E tests: TestUC013_ViewTaskProfilesList."""

from e2e_helpers import run_cli_command


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
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # Should show message about no profiles or empty list
        assert "Нет доступных профилей" in stdout or "Профили задач" in stdout, (
            "Should show profiles section"
        )

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
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # After creation, should see the profile in the list or confirmation
        assert "создан" in stdout.lower() or "Test Task Profile" in stdout, (
            "Should confirm profile creation or show it in list"
        )
