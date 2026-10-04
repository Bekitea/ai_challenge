"""E2E tests: TestUC005_TC084_087_SettingsBranches."""

from e2e_helpers import _QUICK_CHAT, run_cli_command


class TestUC005_TC084_087_SettingsBranches:
    """TC-084..TC-086: Settings change flow branches (UC-005 A1..A3)."""

    def test_tc_084_decline_settings_change_with_empty_or_other_input(self):
        """
        TC-084: Decline Settings Change With Empty Or Other Input (UC-005 A1)

        Steps:
        1. /settings, press Enter at 'Изменить настройки? (y/n):' -> no
           settings prompts, back to chat prompt.
        2. /settings, enter 'maybe' -> treated as decline.
        3. Settings unchanged, chat loop continues.
        """
        test_input = (
            _QUICK_CHAT + "/settings\n"
            "\n"  # Enter — отказ от изменения
            "/settings\n"
            "maybe\n"  # Любой ввод кроме 'y' — отказ
            "/settings\n"
            "n\n"  # Явный отказ
            "/menu\n"
            "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert stdout.count("--- ТЕКУЩИЕ НАСТРОЙКИ ---") >= 3
        # Ни одного входа в поток изменения настроек
        assert "НАСТРОЙКИ ДЛЯ" not in stdout
        assert "Настройки обновлены" not in stdout
        assert "Traceback" not in stderr

    def test_tc_085_invalid_input_during_settings_reprompting(self):
        """
        TC-085: Invalid Input During Settings Re-Prompting (UC-005 A2)

        Steps:
        1. /settings -> 'y' -> all settings prompts re-displayed.
        2. 'abc' at temperature -> 'Некорректное число...' warning, disabled.
        3. '-1' at Top P -> out-of-range warning, disabled.
        4. '-5' at Top K -> 'Top K должен быть >= 0', re-prompted.
        5. Complete flow -> [OK] Настройки обновлены!
        """
        test_input = (
            _QUICK_CHAT + "/settings\n"
            "y\n"
            "\n"  # Модель по умолчанию
            "abc\n"  # Температура: нечисловой ввод
            "-1\n"  # Top P: вне диапазона
            "-5\n"  # Top K: отрицательный -> re-prompt
            "0\n"  # Top K: корректно (отключён)
            "\n"  # Reasoning effort (default)
            "\n"  # Context window (default)
            "/menu\n"
            "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "НАСТРОЙКИ ДЛЯ" in stdout, "Change-settings flow must start"
        assert (
            "Некорректное число. Используется значение по умолчанию (отключено)."
            in stdout
        )
        assert (
            "Top P должен быть от 0.0 до 1.0. Используется значение по умолчанию (отключено)."
            in stdout
        )
        assert "Top K должен быть >= 0" in stdout
        assert "[OK] Настройки обновлены!" in stdout
        assert "Температура: отключена" in stdout
        assert "Top P: отключен" in stdout
        assert "Traceback" not in stderr

    def test_tc_086_eof_during_settings_flow(self):
        """
        TC-086: KeyboardInterrupt During Settings Flow (UC-005 A3)

        EOF mid-flow (emulating Ctrl+C per guide limitations): the chat loop
        handler treats EOFError like KeyboardInterrupt, prints
        'Прервано пользователем.', saves agent memory and exits to the Main
        Menu instead of leaking an error/traceback.
        """
        test_input = (
            _QUICK_CHAT + "/settings\n" + "y\n" + "\n"  # Модель
            # EOF здесь: прерывание посреди потока настроек
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert "Прервано пользователем." in stdout, (
            "UC-005 A3: interruption must print 'Прервано пользователем.'"
        )
        assert returncode == 0, f"App exited with code {returncode}"
        assert "Traceback" not in stderr


