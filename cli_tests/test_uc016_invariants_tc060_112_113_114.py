"""E2E tests: TestUC016_Invariants_TC060_112_113_114."""

from e2e_helpers import run_cli_command


class TestUC016_Invariants_TC060_112_113_114:
    """
    TC-060, TC-112, TC-113, TC-114: Invariant management (UC-016).
    """

    _PROFILE_SETUP = (
        "3\n"  # Профили задач
        "1\n"  # Создать профиль
        "Inv Profile\n"  # Название
        "Profile for invariants\n"  # Описание
        "\n"  # Предпочтения (пропуск)
        "Base rule\n"  # Инвариант при создании
        "\n"  # Пустая строка завершает ввод инвариантов
    )

    def test_tc_060_manage_invariants_add_and_remove(self):
        """
        TC-060: Manage Invariants - Add and Remove (UC-016)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "1\n"  # Добавить инвариант
            "Second rule\n"
            "2\n"  # Удалить инвариант
            "2\n"  # Номер удаляемого (существующий)
            "2\n"  # Удалить инвариант (повторно)
            "99\n"  # Некорректный номер
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку -> возврат в меню профилей
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "ИНВАРИАНТЫ ПРОФИЛЯ" in stdout
        assert "Инвариант добавлен" in stdout
        assert "Инвариант удал" in stdout
        assert "Некорректный номер" in stdout

    def test_tc_112_manage_invariants_empty_text(self):
        """
        TC-112: Manage Invariants - Empty Invariant Text (UC-016 A1)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "1\n"  # Добавить инвариант
            "\n"  # Пустой текст
            "1\n"  # Добавить инвариант (повтор)
            "Valid rule\n"
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "не может быть пустым" in stdout
        assert "Инвариант добавлен" in stdout

    def test_tc_113_manage_invariants_invalid_action(self):
        """
        TC-113: Manage Invariants - Invalid Action Choice Re-Prompts (UC-016 A4)

        Steps:
        1. Open invariants submenu -> list + prompt `Выберите действие (1-3):`
        2. Enter "9" (outside 1-3) -> `[WARN] Неверный выбор.`, re-displayed
        3. Enter "abc" -> same warning, re-displayed
        4. Enter "3" (Назад) -> back to Task Profiles menu
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "9\n"  # Недопустимое действие
            "abc\n"  # Нечисловое действие
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "ИНВАРИАНТЫ ПРОФИЛЯ" in stdout
        # UC-016 A4: warning shown once per invalid input...
        assert "[WARN] Неверный выбор." in stdout
        assert stdout.count("[WARN] Неверный выбор.") >= 2
        # ...and the list/action prompt is re-displayed after each warning
        assert stdout.count("Выберите действие (1-3):") >= 3
        # Step 4: valid action returns control to the Task Profiles menu
        assert "МЕНЮ ПРОФИЛЕЙ ЗАДАЧ" in stdout or "Действия:" in stdout

    def test_tc_114_manage_invariants_remove_with_empty_list(self):
        """
        TC-114: Manage Invariants - Remove With Empty List (UC-016 A5)

        Steps:
        1. Open invariants submenu for a profile with no invariants
           -> `(инварианты не заданы)` and actions displayed
        2. Select action 2 (Удалить инвариант)
           -> `[WARN] Нет инвариантов для удаления.`; removal number
           prompt NOT shown (UC-016 A5)
        3. Verify display -> list and action prompt re-displayed
        4. Add an invariant, then select action 2
           -> removal prompt `Выберите номер инварианта для удаления` now shown
        """
        # Профиль БЕЗ инвариантов (пустая строка сразу завершает их ввод)
        empty_profile_setup = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Empty Inv Profile\n"  # Название
            "Profile without invariants\n"  # Описание
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пусто
        )
        test_input = (
            empty_profile_setup + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "2\n"  # Удалить инвариант при пустом списке
            "1\nRule A\n"  # Добавить инвариант
            "1\nRule B\n"  # Добавить ещё один
            "2\n"  # Удалить инвариант (теперь промпт номера должен появиться)
            "1\n"  # Номер удаляемого
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # Step 1: empty list marker displayed
        assert "(инварианты не заданы)" in stdout
        # Step 2 (UC-016 A5): warning shown exactly once...
        assert "[WARN] Нет инвариантов для удаления." in stdout
        assert stdout.count("[WARN] Нет инвариантов для удаления.") == 1
        # ...and BEFORE any removal-number prompt appears
        warn_idx = stdout.find("Нет инвариантов для удаления")
        prompt_idx = stdout.find("Выберите номер инварианта для удаления")
        assert warn_idx != -1 and prompt_idx != -1
        assert warn_idx < prompt_idx
        # Step 3: submenu re-displayed after the warning (header shown again)
        assert stdout.count("ИНВАРИАНТЫ ПРОФИЛЯ") >= 2
        # Step 4: after adding invariants the removal prompt is shown
        assert "Выберите номер инварианта для удаления (1-2)" in stdout
        assert "Инвариант добавлен" in stdout
        assert "Инвариант удал" in stdout
