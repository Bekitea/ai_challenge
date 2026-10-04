"""E2E tests: TestUC002_Alt_TC076_077_ChatListValidation."""

from e2e_helpers import run_cli_command


class TestUC002_Alt_TC076_077_ChatListValidation:
    """
    TC-076/TC-077: Chat list selection validation (UC-002 A2/A3).
    """

    def test_tc_076_chat_list_selection_out_of_range(self):
        """
        TC-076: Chat List Selection Out Of Range (UC-002 A2)

        Two chats exist; entering "0" then "3" re-prompts with
        "Введите число от 1 до 2"; "1" selects the chat.
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # Настройки по умолчанию
            "/menu\n"  # В меню
            "1\n"  # Новый чат №2
            "\n"  # По умолчанию
            "/menu\n"  # В меню
            "2\n"  # Выбрать чат
            "0\n"  # Вне диапазона снизу
            "3\n"  # Вне диапазона сверху
            "1\n"  # Корректный выбор
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите число от 1 до 2" in stdout
        assert stdout.count("Введите число от 1 до 2") >= 2

    def test_tc_077_chat_list_non_numeric_selection(self):
        """
        TC-077: Chat List Non-Numeric Selection (UC-002 A3)

        Entering "abc" and "2.5" re-prompts with "Введите корректное число";
        a valid number then loads the chat.
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            "/menu\n"  # В меню
            "2\n"  # Выбрать чат
            "abc\n"  # Нечисловой ввод
            "2.5\n"  # Нечисловой ввод (int() падает)
            "1\n"  # Корректный выбор
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите корректное число" in stdout
        assert stdout.count("Введите корректное число") >= 2
