"""E2E tests: TestUC001_ChatCreationWithTaskProfile."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_agent_profile_id, get_profile_by_name


class TestUC001_ChatCreationWithTaskProfile:
    """
    Use Case: Create Chat with Task Profile Selection

    Test Cases:
    - TC-061: Create Chat with Task Profile Attachment
    - TC-062: Create Chat Without Task Profile
    - TC-007: Task Profile Selection Invalid Choice
    """

    def test_tc_061_create_chat_with_task_profile_attachment(self):
        """
        TC-061: Create Chat with Task Profile Attachment

        Steps:
        1. Create a task profile first
        2. Create new chat
        3. Fill in all chat settings
        4. When prompted for task profile, select the created profile
        5. Verify chat created with profile info displayed
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Chat Profile\n"  # Name
            "For chat binding\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "\n"  # MCP-серверы: пропуск
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Bound Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # Strategy
            "1\n"  # Select profile 1 (Chat Profile)
            "/info\n"  # Проверка привязки профиля
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        profile = get_profile_by_name("Chat Profile")
        assert profile is not None
        assert get_agent_profile_id("Bound Chat") == profile["id"]

    def test_tc_062_create_chat_without_task_profile(self):
        """
        TC-062: Create Chat Without Task Profile

        Steps:
        1. Create new chat
        2. Fill in all settings
        3. When prompted for task profile, select 0 (none)
        4. Verify chat created without profile
        5. Verify confirmation shows no profile attached
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "No Profile Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            # Профилей нет -> шаг привязки пропускается автоматически (TC-063)
            "/info\n"  # Проверка отсутствия профиля
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "(нет доступных профилей)" in stdout
        assert get_agent_by_name("No Profile Chat") is not None
        assert get_agent_profile_id("No Profile Chat") is None

    def test_tc_007_task_profile_selection_invalid_choice(self):
        """
        TC-007: Task Profile Selection Invalid Choice

        Steps:
        1. Create a task profile (so the selection list is not empty)
        2. Create new chat via manual path
        3. When prompted for task profile, enter invalid number "99"
        4. Verify [WARN] message and that creation continues without profile
        5. Verify chat created
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "TC007 Profile\n"  # Name
            "Profile for TC-007\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "\n"  # MCP-серверы: пропуск
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Invalid Select Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "99\n"  # Некорректный номер профиля (вне диапазона)
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[WARN] Некорректный выбор. Профиль не привязан." in stdout
        assert get_profile_by_name("TC007 Profile") is not None
        assert get_agent_by_name("Invalid Select Chat") is not None
        assert get_agent_profile_id("Invalid Select Chat") is None
