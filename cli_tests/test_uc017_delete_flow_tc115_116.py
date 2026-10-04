"""E2E tests: TestUC017_DeleteFlow_TC115_116."""

from e2e_helpers import run_cli_command


class TestUC017_DeleteFlow_TC115_116:
    """
    TC-115/TC-116: Task profile deletion edge cases (UC-017).
    """

    _PROFILE_SETUP = (
        "3\n"  # Профили задач
        "1\n"  # Создать профиль
        "Del Target\n"  # Название
        "To be deleted\n"  # Описание
        "\n"  # Предпочтения
        "\n"  # Инварианты: пусто
    )

    def test_tc_115_chat_loop_graceful_exit_on_eof(self):
        """
        TC-115: Chat Loop Graceful Exit On End Of Input (UC-004 A7)

        Steps:
        1. Create a chat (quick path), send one message; input ends right
           after the exchange (no /menu, no option 6).
        2. Verify termination: no traceback, clean exit.
        3. Verify memory save: agent memory is saved before exit (restart
           shows the exchange intact).
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            "Remember this fact\n"  # Сообщение
            "\n"  # Отказ от рассуждений (если запрошен)
            # EOF: stdin закрывается прямо в цикле чата
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[AGENT]" in stdout, "Message exchange should complete before EOF"
        assert "Traceback" not in stderr
        assert "EOFError" not in stderr

        # Шаг 3: память сохранена — перезапуск показывает тот же чат с историей
        restart_input = (
            "2\n"  # Выбрать чат
            "1\n"  # Чат 1
            "/info\n"  # Проверка счётчика сообщений
            "/menu\n"
            "6\n"
        )
        stdout2, stderr2, rc2 = run_cli_command(restart_input)
        assert rc2 == 0, f"Restart failed: {stderr2}"
        assert "[OK] Выбран чат: Чат 1" in stdout2
        import re as _re

        m = _re.search(r"Сообщений:\s*(\d+)", stdout2)
        assert m is not None, f"No message counter in /info output:\n{stdout2}"
        assert int(m.group(1)) >= 2, (
            "Memory must be saved on EOF exit: expected user+assistant "
            f"messages persisted, got {m.group(1)}"
        )

    def test_tc_116_profiles_submenu_non_numeric_action_reprompts(self):
        """
        TC-116: Profiles List Submenu Non-Numeric Action Re-Prompts (UC-013 A4)

        Steps:
        1. Open profiles list with at least one profile -> prompt
           'Выберите действие (1-4):' displayed.
        2. Enter 'abc' (non-numeric) -> [WARN] Неверный выбор, попробуйте снова.,
           action prompt re-displayed.
        3. Enter '0' -> same warning; action prompt re-displayed.
        4. Enter '4' (Back to list) -> control returns to the Task Profiles menu.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "abc\n"  # Нечисловое действие
            "0\n"  # Некорректное действие
            "4\n"  # Назад к списку -> возврат в меню профилей
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Выберите действие (1-4):" in stdout
        # Предупреждения именно из подменю действий (после вывода списка профилей)
        after_list = stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---", 1)[-1]
        assert after_list.count("[WARN] Неверный выбор, попробуйте снова.") >= 2, (
            "'abc' and '0' must each produce the invalid-choice warning"
        )
        # После шага 4 управление вернулось в меню профилей (его заголовок)
        assert "--- ПРОФИЛИ ЗАДАЧ ---" in stdout
        assert "успешно удалён" not in stdout
        assert "Del Target" in stdout

    def test_tc_117_create_profile_with_empty_preferences(self):
        """
        TC-117: Create Profile With Empty Preferences (UC-014 A3)

        Steps:
        1. Reach the preferences prompt during profile creation.
        2. Press Enter (empty input) -> no error, invariants block follows.
        3. Finish creation with an empty invariants line -> [OK] message.
        4. View the created profile (action 1) -> 'Предпочтения:' omitted.
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "EmptyPrefs117\n"  # Название
            "Profile with empty prefs\n"  # Описание
            "\n"  # Предпочтения: пустой ввод (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите предпочтения/инструкции (Enter для пропуска):" in stdout
        assert "--- ИНВАРИАНТЫ" in stdout, "Invariants block must follow skipped prefs"
        assert "[OK] Профиль задачи 'EmptyPrefs117' создан!" in stdout
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        # §4.7.3: при пустых предпочтениях строка 'Предпочтения:' не выводится
        assert "Предпочтения:" not in stdout

    def test_tc_118_delete_task_profile_repository_failure(self):
        """
        TC-118: Delete Task Profile - Repository Failure (UC-017 step 7)

        Uses the TEST-only fault-injection hook TEST_FAIL_DELETE_PROFILE=1
        (use_cases.DeleteTaskProfileUseCase) so that profile deletion returns
        False, which cli_app._delete_profile reports as
        "[ERROR] Не удалось удалить профиль '{name}.'". The profile must stay
        in the list afterwards.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "1\n"  # Профиль №1
            "y\n"  # Подтвердить удаление (репозиторий «падает»)
            "4\n"  # Назад к списку -> возврат в меню профилей
            "2\n"  # Просмотреть список снова — профиль должен остаться
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(
            test_input, extra_env={"TEST_FAIL_DELETE_PROFILE": "1"}
        )

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert (
            "Вы уверены, что хотите удалить профиль 'Del Target'? (y/n):" in stdout
        ), "Confirmation prompt text must match UC-017 step 6"
        assert "[ERROR] Не удалось удалить профиль 'Del Target'." in stdout, (
            "Failed deletion must print the exact error from cli_app._delete_profile"
        )
        assert "успешно удалён" not in stdout
        # Шаг 3 TC-118: профиль остаётся доступным в списке
        assert "Del Target" in stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---")[-1], (
            "Profile must remain in the list after a failed deletion"
        )
        assert "Traceback" not in stderr

    def test_tc_115b_delete_profile_invalid_index(self):
        """
        Supplement (UC-017): Out-of-range and non-numeric delete indices must
        not crash the app and must keep the profile intact.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "99\n"  # Вне диапазона
            "abc\n"  # Нечисловой ввод
            "1\n"  # Профиль №1
            "n\n"  # Отменить удаление — профиль остаётся
            "4\n"  # Назад к списку -> возврат в меню профилей
            "0\n"  # Выход из подменю списка (см. _view_task_profiles_list)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите корректное число" in stdout, (
            "Non-numeric delete index must re-prompt without crashing"
        )
        assert "[INFO] Удаление отменено." in stdout
        assert "Del Target" in stdout
        assert "успешно удалён" not in stdout
        assert "Traceback" not in stderr

    def test_tc_116b_delete_last_profile_refreshes_list(self):
        """
        Supplement (UC-017): After deleting the only profile the submenu stays
        usable and the list shows the empty state.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "1\n"  # Профиль №1
            "y\n"  # Подтвердить удаление
            "2\n"  # Просмотреть список снова (подменю доступно после удаления)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль 'Del Target' успешно удалён." in stdout
        assert "Нет доступных профилей задач." in stdout
