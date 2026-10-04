"""E2E tests: TestUC017_DeleteTaskProfile."""

from e2e_helpers import run_cli_command


class TestUC017_DeleteTaskProfile:
    """
    Use Case UC-016: Delete Task Profile

    Test Cases:
    - TC-057: Delete Task Profile (Not Attached)
    - TC-058: Delete Task Profile (Attached to Agents)
    - TC-059: Delete Task Profile (Cancelled)
    """

    def test_tc_057_delete_task_profile_not_attached(self):
        """
        TC-057: Delete Task Profile - Not Attached

        Steps:
        1. Create a task profile
        2. Select delete option
        3. Confirm deletion
        4. Verify success message
        5. Verify profile removed from list
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "ToDelete Profile\n"  # Name
            "Will be deleted\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: удалить профиль
            "1\n"  # Профиль №1 для удаления
            "y\n"  # Подтверждение удаления
            "2\n"  # Снова открыть список профилей
            "4\n"  # Действие: назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'ToDelete Profile' создан!" in stdout
        assert "[OK] Профиль 'ToDelete Profile' успешно удалён." in stdout
        # Profile removed from the subsequent list
        assert "Нет доступных профилей задач." in stdout

    def test_tc_058_delete_task_profile_attached_to_agents(self):
        """
        TC-058: Delete Task Profile - Attached to Agents

        Steps:
        1. Create a task profile
        2. Create a chat linked to this profile
        3. Try to delete the profile
        4. Verify warning about linked agents
        5. Verify deletion still possible or blocked
        """
        # This test requires full flow: create profile, create chat with profile, delete
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Linked Profile\n"  # Name
            "Has linked chats\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат (привязка к профилю)
            "y\n"  # Хотите настроить? (y/n)
            "Linked Chat\n"  # Chat name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "1\n"  # Привязать профиль №1 (Linked Profile)
            "/menu\n"  # Выход из чата в меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: удалить профиль
            "1\n"  # Профиль №1 для удаления
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Linked Chat' создан!" in stdout
        # TC-058/UC-017 A?: deletion blocked because profile is attached to an agent
        assert "Невозможно удалить профиль 'Linked Profile'" in stdout
        assert "Сначала удалите или пересоздайте агентов" in stdout

    def test_tc_059_delete_task_profile_cancelled(self):
        """
        TC-059: Delete Task Profile - Cancelled

        Steps:
        1. Create a task profile
        2. Select delete option
        3. When prompted for confirmation, select 'no'
        4. Verify profile NOT deleted
        5. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Keep Profile\n"  # Name
            "Should not be deleted\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: Удалить профиль
            "1\n"  # Выбрать профиль №1 для удаления
            "n\n"  # Подтверждение удаления: нет (отмена)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[INFO] Удаление отменено." in stdout
        assert "успешно удалён" not in stdout
        # Профиль остался в списке
        assert "Keep Profile" in stdout
