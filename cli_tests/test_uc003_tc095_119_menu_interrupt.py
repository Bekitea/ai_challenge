"""E2E tests: TestUC003_TC095_119_MenuInterrupt."""

from e2e_helpers import run_cli_command


class TestUC003_TC095_119_MenuInterrupt:
    """TC-095/TC-119: Ctrl+C / EOF at the Main Menu prompt (UC-003 A2)."""

    def test_tc_095_ctrl_c_at_menu_prompt_exits_cleanly(self):
        """
        TC-095: Return To Active Chat - Ctrl+C At Menu Prompt (UC-003 A2)

        EOF at 'Ваш выбор (1-6):' (emulated Ctrl+C) -> 'До свидания!', clean
        termination, no traceback.
        """
        test_input = (
            "1\n"  # Создать чат быстрым путём
            + "\n"
            + "/menu\n"  # Вернуться в главное меню
            # EOF на промпте меню
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "До свидания!" in stdout
        assert "Traceback" not in stderr
        assert "EOFError" not in stderr

    def test_tc_119_return_to_active_chat_after_eof_at_menu(self):
        """
        TC-119: Return To Active Chat After EOF At Menu Prompt (UC-003 A2)

        Steps:
        1. Create a chat, return to menu; option 5 enters the active chat.
        2. Back at the menu, EOF -> 'До свидания!', clean exit.
        3. Restart -> the chat is still present and selectable via option 2.
        """
        first_run = (
            "1\n"  # Новый чат (быстрый путь)
            + "\n"
            + "/menu\n"  # В главное меню
            + "5\n"  # Шаг 1: возврат в чат через опцию 5
            + "/menu\n"
            # Шаг 2: EOF на промпте меню
        )

        stdout, stderr, returncode = run_cli_command(first_run)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[OK] Возврат в чат: Чат 1" in stdout
        assert "До свидания!" in stdout
        assert "Traceback" not in stderr

        # Шаг 3: рестарт — чат сохранён и доступен через опцию 2
        restart_input = "2\n1\n/info\n/menu\n6\n"
        stdout2, stderr2, rc2 = run_cli_command(restart_input)
        assert rc2 == 0, f"Restart failed: {stderr2}"
        assert "[OK] Выбран чат: Чат 1" in stdout2
        assert "Название: Чат 1" in stdout2
