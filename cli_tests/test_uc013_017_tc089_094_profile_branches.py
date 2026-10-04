"""E2E tests: TestUC013_017_TC089_094_ProfileBranches."""

from e2e_helpers import run_cli_command


class TestUC013_017_TC089_094_ProfileBranches:
    """
    TC-089..TC-094: Task profile flows validation/failure branches
    (UC-013 A2-A4, UC-014 A4, UC-015 A1/A3, UC-016 A3, UC-017 A1).
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
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "--- ИНВАРИАНТЫ (строгие правила/ограничения) ---" in stdout
        assert "[OK] Профиль задачи 'NoInvProfile' создан!" in stdout
        assert "ID:" in stdout
        assert "Дата создания:" in stdout
        assert "Инвариантов:" not in stdout, (
            "Count line must be omitted when no invariants were entered"
        )

    def test_tc_090_manage_invariants_repository_valueerror_on_add(self):
        """
        TC-090: Manage Invariants - Repository ValueError On Add (UC-016 A3)

        TEST_FAIL_ADD_INVARIANT=1 makes add_invariant raise ValueError;
        expected '[ERROR] {e}', nothing added, list redisplayed.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "2\n"  # Управление инвариантами
            + "1\n"  # Профиль №1
            + "1\n"  # Добавить инвариант
            + "Duplicate rule\n"  # Вызовет ValueError (fault injection)
            + "3\n"  # Назад из подменю инвариантов
            + "4\n"  # Назад к списку
            + "3\n"  # Назад в главное меню
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(
            test_input, extra_env={"TEST_FAIL_ADD_INVARIANT": "1"}
        )

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Инвариант уже существует (TEST)" in stdout
        assert "[OK] Инвариант добавлен!" not in stdout
        # Список перерисован: единственный исходный инвариант виден,
        # добавленный отсутствует
        inv_block = stdout.split("--- ИНВАРИАНТЫ ПРОФИЛЯ: Rule A Profile ---", 1)[-1]
        assert "Rule A" in inv_block
        assert "Duplicate rule" not in inv_block
        assert "Traceback" not in stderr

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
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        profiles_menu_part = stdout.split("--- ПРОФИЛИ ЗАДАЧ ---")[1]
        assert "[WARN] Неверный выбор, попробуйте снова." in profiles_menu_part
        submenu_part = stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---", 1)[-1]
        assert "[WARN] Неверный выбор, попробуйте снова." in submenu_part
        assert "Введите число от 1 до 1" in submenu_part
        assert "Введите корректное число" in submenu_part
        # Шаг 5: действие выполнено — просмотр памяти профиля
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Traceback" not in stderr

    def test_tc_092_view_task_profile_memory_not_found(self):
        """
        TC-092: View Task Profile Memory - Profile Not Found (UC-015 A3)

        Two profiles exist; delete the second one while its entry remains in
        the stale submenu snapshot, then view memory with that stale index ->
        repository returns None -> '[ERROR] Профиль не найден.' and control
        returns to the Task Profiles menu.
        """
        test_input = (
            self._PROFILE_SETUP  # Профиль №1: Rule A Profile
            + "1\n"  # Ещё профиль: Second Profile
            + "Second Profile\n"
            + "Another description\n"
            + "\n"  # Предпочтения
            + "\n"  # Инварианты пусто
            + "2\n"  # Просмотреть список (снимок: 2 профиля)
            + "3\n"  # Удалить профиль
            + "2\n"  # Профиль №2 (Second Profile)
            + "y\n"  # Подтвердить удаление
            + "2\n"  # Просмотреть список -> устаревший снимок с 2 записями
            + "1\n"  # Действие: просмотр памяти
            + "2\n"  # Ставший несуществующим профиль №2
            + "3\n"  # Назад в главное меню (после ошибки вернулись туда)
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль 'Second Profile' успешно удалён." in stdout
        assert "[ERROR] Профиль не найден." in stdout
        # Шаг 3: управление вернулось в меню профилей (заголовок виден
        # после сообщения об ошибке)
        after_error = stdout.split("[ERROR] Профиль не найден.", 1)[-1]
        assert "--- ПРОФИЛИ ЗАДАЧ ---" in after_error
        assert "Traceback" not in stderr

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
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Выберите профиль для удаления (1-1):" in stdout
        assert "Введите число от 1 до 1" in stdout
        assert "Введите корректное число" in stdout
        assert (
            "Вы уверены, что хотите удалить профиль 'Rule A Profile'? (y/n):" in stdout
        )
        assert "[INFO] Удаление отменено." in stdout
        assert "успешно удалён" not in stdout
        assert "Traceback" not in stderr

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
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Выберите профиль (1-1):" in stdout
        assert "Введите число от 1 до 1" in stdout
        assert "Введите корректное число" in stdout
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Название: Rule A Profile" in stdout
        assert "Traceback" not in stderr
