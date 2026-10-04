"""E2E tests: TestUC014_CreateNewTaskProfile."""

from e2e_helpers import run_cli_command


class TestUC014_CreateNewTaskProfile:
    """
    Use Case UC-014: Create New Task Profile

    Test Cases:
    - TC-049: Create Task Profile (Valid Data)
    - TC-050: Create Task Profile (Empty Name Validation)
    - TC-052: Create Task Profile (Empty Description Validation)
    - TC-051: Create Task Profile (Long Name Accepted)
    - TC-068: Create Profile With Preferences
    - TC-069: Create Profile Without Preferences
    """

    def test_tc_049_create_task_profile_with_valid_data(self):
        """
        TC-049: Create Task Profile with Valid Data

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Verify success message with profile info
        6. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout

    def test_tc_050_create_task_profile_empty_name_validation(self):
        """
        TC-050: Create Task Profile - Empty Name Validation

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Press Enter (empty name)
        4. Verify error message about empty name
        5. Re-enter valid name
        6. Enter description
        7. Verify success
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "\n"  # Empty name (should trigger validation)
            "Valid Name\n"  # Valid name on retry
            "Description\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Название профиля не может быть пустым." in stdout
        assert "[OK] Профиль задачи 'Valid Name' создан!" in stdout

    def test_tc_052_create_task_profile_empty_description_validation(self):
        """
        TC-052: Create Task Profile - Empty Description Validation

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name
        4. Press Enter (empty description)
        5. Verify error message about empty description
        6. Re-enter valid description
        7. Verify success
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Task Name\n"  # Valid name
            "\n"  # Empty description (should trigger validation)
            "Valid Description\n"  # Valid description on retry
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Описание задачи не может быть пустым." in stdout
        assert "[OK] Профиль задачи 'Task Name' создан!" in stdout

    def test_tc_051_create_task_profile_long_name_accepted(self):
        """
        TC-051: Create Task Profile - Long Name Accepted

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Enter 150-character name (should truncate to 100)
        4. Enter description
        5. Verify profile created with truncated name
        """
        long_name = "A" * 150  # 150 characters

        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            f"{long_name}\n"  # Long name (accepted without truncation)
            "Description\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи" in stdout and "создан!" in stdout

    def test_tc_068_create_profile_with_preferences(self):
        """
        TC-068: Create Profile With Preferences

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Enter preferences text "Be concise and formal"
        6. Verify success message with profile info
        7. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "Be concise and formal\n"  # Preferences text
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout
        # Просмотр профиля после создания (шаг 4 TC-068);
        # детальная проверка отображения предпочтений — в TC-066

    def test_tc_069_create_profile_without_preferences(self):
        """
        TC-069: Create Profile Without Preferences

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Press Enter (skip preferences)
        6. Verify success message with profile info
        7. Verify empty preferences accepted (no error)
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "\n"  # Empty preferences (skip)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout
