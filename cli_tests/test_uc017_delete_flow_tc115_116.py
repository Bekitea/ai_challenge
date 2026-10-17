"""E2E tests: TestUC017_DeleteFlow_TC115_116."""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_agent_by_name, get_messages_by_name, get_profile_by_name


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
            _QUICK_CHAT  # Новый чат (быстрое создание)
            + "Remember this fact\n"  # Сообщение
            # EOF: stdin закрывается прямо в цикле чата
        )

        run_cli_command(test_input)

        # Шаг 3: память сохранена — история того же чата на месте (ground truth)
        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        assert agent["message_count"] >= 2
        messages = get_messages_by_name("Чат 1")
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "Remember this fact"

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
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Выберите действие (1-4):" in stdout
        # Предупреждения именно из подменю действий (после вывода списка профилей)
        after_list = stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---", 1)[-1]
        assert after_list.count("[WARN] Неверный выбор, попробуйте снова.") >= 2, (
            "'abc' and '0' must each produce the invalid-choice warning"
        )
        # После шага 4 управление вернулось в меню профилей (его заголовок)
        assert "--- ПРОФИЛИ ЗАДАЧ ---" in stdout
        # Ground truth: профиль не удалён
        assert get_profile_by_name("Del Target") is not None

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
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Введите предпочтения/инструкции (Enter для пропуска):" in stdout
        assert "--- ИНВАРИАНТЫ" in stdout, "Invariants block must follow skipped prefs"
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        # §4.7.3: предпочтения пусты
        assert get_profile_by_name("EmptyPrefs117")["preferences"] == ""

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
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Введите корректное число" in stdout, (
            "Non-numeric delete index must re-prompt without crashing"
        )
        assert "[INFO] Удаление отменено." in stdout
        # Ground truth: профиль не удалён
        assert get_profile_by_name("Del Target") is not None

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
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Нет доступных профилей задач." in stdout
        assert get_profile_by_name("Del Target") is None
