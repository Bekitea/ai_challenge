"""E2E tests: TestUC001_TC063_120_CreationExtras."""

from e2e_helpers import _manual_chat, run_cli_command


class TestUC001_TC063_120_CreationExtras:
    """TC-063: profile-less creation; TC-120: quick-path default name counter."""

    def test_tc_063_task_profile_selection_no_profiles_available(self):
        """
        TC-063: Task Profile Selection - No Profiles Available (UC-001 §4.4.10)

        Precondition: no task profiles exist. Manual creation reaching the
        profile step must print '(нет доступных профилей)' and continue
        without attachment.
        """
        test_input = (
            _manual_chat("NoProfilesChat")
            + "/info\n"  # Профиль не привязан
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---" in stdout
        assert "(нет доступных профилей)" in stdout
        assert "[OK] Чат 'NoProfilesChat' создан!" in stdout
        assert "Профиль задачи: (не привязан)" in stdout
        assert "Traceback" not in stderr

    def test_tc_120_quick_creation_default_name_counter(self):
        """
        TC-120: Quick Creation Default Name Counter (UC-001 A1, A3)

        Steps:
        1. Ensure exactly 2 chats exist (two quick chats).
        2. Option 1, Enter at configure prompt -> defaults announced.
        3. Completion message names the chat 'Чат 3' (N = existing + 1).
        4. Defaults applied (model, disabled params, DefaultStrategy, no profile).
        """
        test_input = (
            "1\n\n/menu\n"  # Чат 1
            + "1\n\n/menu\n"  # Чат 2
            + "1\n"  # Третий чат
            + "\n"  # Enter на 'Хотите настроить?' -> быстрый путь
            + "/settings\n"
            + "n\n"
            + "/info\n"
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Используются настройки по умолчанию." in stdout
        assert "[OK] Чат 'Чат 3' создан!" in stdout
        assert "Модель: aliceai-llm-flash/latest" in stdout
        assert "Температура: отключена" in stdout
        assert "Top P: отключен" in stdout
        assert "Top K: отключено" in stdout
        assert "Размер контекстного окна: 200000 токенов" in stdout
        assert "Стратегия: DefaultStrategy" in stdout
        assert "Профиль задачи: (не привязан)" in stdout
