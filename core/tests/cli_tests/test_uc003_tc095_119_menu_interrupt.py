"""E2E tests: TestUC003_TC095_119_MenuInterrupt."""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_agent_by_name


class TestUC003_TC095_119_MenuInterrupt:
    """TC-095/TC-119: Ctrl+C / EOF at the Main Menu prompt (UC-003 A2)."""

    def test_tc_095_ctrl_c_at_menu_prompt_exits_cleanly(self):
        """
        TC-095: Return To Active Chat - Ctrl+C At Menu Prompt (UC-003 A2)

        EOF at 'Ваш выбор (1-8):' (emulated Ctrl+C) -> 'До свидания!', clean
        termination, no traceback.
        """
        test_input = (
            _QUICK_CHAT  # Создать чат быстрым путём
            + "/menu\n"  # Вернуться в главное меню
            # EOF на промпте меню
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "До свидания!" in stdout

    def test_tc_119_return_to_active_chat_after_eof_at_menu(self):
        """
        TC-119: Return To Active Chat After EOF At Menu Prompt (UC-003 A2)

        Steps:
        1. Create a chat, return to menu; option 5 enters the active chat.
        2. Back at the menu, EOF -> 'До свидания!', clean exit.
        3. Restart -> the chat is still present and selectable via option 2.
        """
        first_run = (
            _QUICK_CHAT  # Новый чат (быстрый путь)
            + "/menu\n"  # В главное меню
            + "5\n"  # Шаг 1: возврат в чат через опцию 5
            + "/menu\n"
            # Шаг 2: EOF на промпте меню
        )

        stdout, _, _ = run_cli_command(first_run)

        assert "[OK] Возврат в чат: Чат 1" in stdout
        assert "До свидания!" in stdout

        # Шаг 3: рестарт — чат сохранён и доступен через опцию 2
        restart_input = "2\n1\n/info\n/menu\n8\n"
        stdout2, _, _ = run_cli_command(restart_input)
        assert "[OK] Выбран чат: Чат 1" in stdout2
        assert get_agent_by_name("Чат 1") is not None
