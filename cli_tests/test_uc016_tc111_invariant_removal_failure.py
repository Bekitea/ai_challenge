"""E2E tests: TestUC016_TC111_InvariantRemovalFailure."""

from e2e_helpers import run_cli_command


class TestUC016_TC111_InvariantRemovalFailure:
    """TC-111: Manage Invariants - Removal Failure Message (UC-016 A2)."""

    _PROFILE_SETUP = (
        "3\n"
        "1\n"
        "Removable Inv\n"
        "Invariant removal failure target\n"
        "\n"  # Предпочтения
        "Keep rule\n"  # Инвариант
        "\n"
    )

    def test_tc_111_manage_invariants_removal_failure(self):
        """
        TC-111: Manage Invariants - Removal Failure Message (UC-016 A2)

        TEST_FAIL_REMOVE_INVARIANT=1 makes remove_invariant return False for
        any valid number -> '[ERROR] Не удалось удалить инвариант.', the
        invariant remains in the list.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список
            + "2\n"  # Управление инвариантами
            + "1\n"  # Профиль №1
            + "2\n"  # Удалить инвариант
            + "1\n"  # Номер 1 (синтаксически корректный, удаление «падает»)
            + "3\n"  # Назад из подменю
            + "4\n"  # Назад к списку
            + "3\n"  # Назад в главное меню
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(
            test_input, extra_env={"TEST_FAIL_REMOVE_INVARIANT": "1"}
        )

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Выберите номер инварианта для удаления (1-1):" in stdout, (
            "Removal prompt must be displayed (step 1)"
        )
        assert "[ERROR] Не удалось удалить инвариант." in stdout
        assert "[OK] Инвариант удалён!" not in stdout
        # Инвариант остался в списке (перерисованный блок)
        last_block = stdout.rsplit("--- ИНВАРИАНТЫ ПРОФИЛЯ: Removable Inv ---", 1)[-1]
        assert "Keep rule" in last_block
        assert "Traceback" not in stderr
