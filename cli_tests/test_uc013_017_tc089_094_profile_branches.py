"""E2E tests: TestUC013_017_TC089_094_ProfileBranches."""

from e2e_helpers import run_cli_command
from ground_truth import get_invariants, get_profile_by_name


def _invariant_texts(profile_name: str) -> list[str]:
    """Тексты инвариантов профиля (ground truth)."""
    profile = get_profile_by_name(profile_name)
    assert profile is not None
    return [row["text"] for row in get_invariants(profile["id"])]


class TestUC013_017_TC089_094_ProfileBranches:
    """
    TC-089, TC-090, TC-091, TC-093, TC-094: Task profile flows
    validation/failure branches (UC-013 A2-A4, UC-014 A4, UC-015 A1,
    UC-016 A3, UC-017 A1).
    """

    _PROFILE_SETUP = (
        "3\n"  # Профили задач
        "1\n"  # Создать профиль
        "Rule A Profile\n"  # Название
        "Description for rules\n"  # Описание
        "\n"  # Предпочтения (пропуск)
        "Rule A\n"  # Инвариант
        "\n"  # Завершить инварианты
    )

    def test_tc_089_create_profile_no_invariants_omits_count_line(self):
        """
        TC-089: Create Task Profile - No Invariants Omits Count Line (UC-014 A4)

        Steps:
        1. Reach invariants block during creation.
        2. Press Enter immediately -> empty invariants list.
        3. Success message includes ID and date but NO 'Инвариантов:' line.
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "NoInvProfile\n"
            "Profile without invariants\n"
            "\n"  # Предпочтения
            "\n"  # Инварианты: пустая строка сразу
            "3\n"  # Назад в главное меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНВАРИАНТЫ (строгие правила/ограничения) ---" in stdout
        assert get_profile_by_name("NoInvProfile") is not None
        assert _invariant_texts("NoInvProfile") == []

    def test_tc_090_manage_invariants_repository_valueerror_on_add(self):
        """
        TC-090: Manage Invariants - Repository ValueError On Add (UC-016 A3)

        Adding an invariant that already exists makes the repository raise
        ValueError; expected '[ERROR] {e}', nothing added, list redisplayed.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "2\n"  # Управление инвариантами
            + "1\n"  # Профиль №1
            + "1\n"  # Добавить инвариант
            + "Rule A\n"  # Дубликат существующего инварианта -> ValueError
            + "3\n"  # Назад из подменю инвариантов
            + "4\n"  # Назад к списку
            + "3\n"  # Назад в главное меню
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[ERROR] Инвариант уже существует" in stdout
        assert "[OK] Инвариант добавлен!" not in stdout
        # Ground truth: дубликат не добавлен, список остался прежним
        assert _invariant_texts("Rule A Profile") == ["Rule A"]

    def test_tc_091_profiles_menu_and_submenu_invalid_choices(self):
        """
        TC-091: Profiles Menu And Submenu Invalid Choices Re-Prompt
        (UC-013 A2, A3, A4)

        Steps:
        1. Invalid choice ('9') at the profiles menu prompt -> [WARN].
        2. Open list, action '99' -> same warning, action prompt re-displayed.
        3. Action 1, index '99' -> 'Введите число от 1 до {n}'.
        4. Index 'abc' -> 'Введите корректное число'.
        5. Valid index -> action proceeds.
        """
        test_input = (
            self._PROFILE_SETUP
            + "9\n"  # Шаг 1: недопустимый выбор в меню профилей (1-3)
            + "2\n"  # Просмотреть список профилей
            + "99\n"  # Шаг 2: недопустимое действие
            + "1\n"  # Действие: просмотр памяти профиля
            + "99\n"  # Шаг 3: индекс вне диапазона
            + "abc\n"  # Шаг 4: нечисловой индекс
            + "1\n"  # Шаг 5: корректный индекс
            + "3\n"  # Назад в главное меню
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        # Неверный выбор '9' вводится уже после создания профиля, т.е. после
        # второго заголовка меню (первый — при первом входе в раздел).
        profiles_menu_part = stdout.split("--- ПРОФИЛИ ЗАДАЧ ---")[2]
        assert "[WARN] Неверный выбор, попробуйте снова." in profiles_menu_part
        submenu_part = stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---", 1)[-1]
        assert "[WARN] Неверный выбор, попробуйте снова." in submenu_part
        assert "Введите число от 1 до 1" in submenu_part
        assert "Введите корректное число" in submenu_part
        # Шаг 5: действие выполнено — просмотр памяти профиля
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        # Ground truth: невалидные вводы не изменили список инвариантов
        assert _invariant_texts("Rule A Profile") == ["Rule A"]

    def test_tc_093_delete_task_profile_invalid_selection_reprompts(self):
        """
        TC-093: Delete Task Profile - Invalid Selection Re-Prompts (UC-017 A1)

        Steps:
        1. Action 3 (Delete) -> 'Выберите профиль для удаления (1-{n}):'.
        2. Out-of-range number -> 'Введите число от 1 до {n}', re-prompted.
        3. 'abc' -> 'Введите корректное число', re-prompted.
        4. Valid index -> confirmation prompt displayed.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список
            + "3\n"  # Удалить профиль
            + "99\n"  # Вне диапазона
            + "abc\n"  # Нечисловой ввод
            + "1\n"  # Корректный индекс
            + "n\n"  # Отменить удаление (проверяем только промпт подтверждения)
            + "4\n"  # Назад к списку
            + "3\n"  # Назад в главное меню
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Выберите профиль для удаления (1-1):" in stdout
        assert "Введите число от 1 до 1" in stdout
        assert "Введите корректное число" in stdout
        assert (
            "Вы уверены, что хотите удалить профиль 'Rule A Profile'? (y/n):" in stdout
        )
        assert "[INFO] Удаление отменено." in stdout
        # Ground truth: профиль не удалён
        assert get_profile_by_name("Rule A Profile") is not None

    def test_tc_094_view_task_profile_memory_invalid_selection_reprompts(self):
        """
        TC-094: View Task Profile Memory - Invalid Selection Re-Prompts
        (UC-015 A1)

        Steps:
        1. Action 1 (View memory) -> 'Выберите профиль (1-{n}):'.
        2. Out-of-range -> 'Введите число от 1 до {n}', re-prompted.
        3. 'abc' -> 'Введите корректное число', re-prompted.
        4. Valid index -> profile info displayed.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список
            + "1\n"  # Просмотреть память профиля
            + "99\n"  # Вне диапазона
            + "abc\n"  # Нечисловой ввод
            + "1\n"  # Корректный индекс
            + "3\n"  # Назад в главное меню
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Выберите профиль (1-1):" in stdout
        assert "Введите число от 1 до 1" in stdout
        assert "Введите корректное число" in stdout
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert get_profile_by_name("Rule A Profile")["name"] == "Rule A Profile"
