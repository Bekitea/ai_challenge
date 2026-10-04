"""E2E tests: TestUC018_TC096_100_Phases."""

from e2e_helpers import _QUICK_CHAT, run_cli_command


class TestUC018_TC096_100_Phases:
    """TC-096..TC-100: Phase transitions via /plan, /execute, /validate, /report."""

    def test_tc_096_phase_forward_transition_plan_to_execute(self):
        """
        TC-096: Phase Command - Forward Transition PLAN to EXECUTE (UC-018)

        Steps:
        1. New chat header shows [Фаза: PLAN].
        2. /execute -> '[INFO] Фаза изменена: PLAN -> EXECUTE'.
        3. Header updated to [Фаза: EXECUTE].
        4. /validate -> 'EXECUTE -> VALIDATE' (sequential forward allowed).
        5. Regular message processed normally in the new phase.
        """
        test_input = (
            _QUICK_CHAT
            + "/execute\n"
            + "/validate\n"
            + "message in validate phase\n"
            + "\n"  # отказ от рассуждений
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "--- ЧАТ: Чат 1 [Фаза: PLAN] ---" in stdout
        assert "[INFO] Фаза изменена: PLAN -> EXECUTE" in stdout
        assert "--- ЧАТ: Чат 1 [Фаза: EXECUTE] ---" in stdout
        assert "[INFO] Фаза изменена: EXECUTE -> VALIDATE" in stdout
        # Шаг 5: обычный обмен состоялся в новой фазе, цикл жив
        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "Traceback" not in stderr

    def test_tc_097_phase_forward_skip_rejected(self):
        """
        TC-097: Phase Command - Forward Skip Rejected (UC-018 A1)

        Steps:
        1. PLAN -> /validate rejected with exact message; header unchanged.
        2. PLAN -> /report rejected; phase remains PLAN.
        3. EXECUTE -> /report rejected; phase remains EXECUTE.
        """
        test_input = (
            _QUICK_CHAT
            + "/validate\n"
            + "/report\n"
            + "/execute\n"
            + "/report\n"
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert (
            "[INFO] Нельзя перескочить этап: переход из PLAN сразу в VALIDATE запрещен"
            in stdout
        )
        assert (
            "[INFO] Нельзя перескочить этап: переход из PLAN сразу в REPORT запрещен"
            in stdout
        )
        assert (
            "[INFO] Нельзя перескочить этап: переход из EXECUTE сразу в REPORT запрещен"
            in stdout
        )
        # Заголовки после отказов показывают прежнюю фазу
        assert "--- ЧАТ: Чат 1 [Фаза: PLAN] ---" in stdout
        assert "--- ЧАТ: Чат 1 [Фаза: EXECUTE] ---" in stdout
        assert "Traceback" not in stderr

    def test_tc_098_phase_backward_transition_allowed(self):
        """
        TC-098: Phase Command - Backward Transition Allowed (UC-018 A2)

        Steps:
        1. Advance to VALIDATE via /execute, /validate.
        2. /plan -> 'VALIDATE -> PLAN' (any backward transition allowed).
        3. Header shows [Фаза: PLAN].
        4. /execute then /plan again -> 'EXECUTE -> PLAN' succeeds.
        """
        test_input = (
            _QUICK_CHAT
            + "/execute\n"
            + "/validate\n"
            + "/plan\n"
            + "/execute\n"
            + "/plan\n"
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[INFO] Фаза изменена: VALIDATE -> PLAN" in stdout
        assert "[INFO] Фаза изменена: EXECUTE -> PLAN" in stdout
        assert "--- ЧАТ: Чат 1 [Фаза: PLAN] ---" in stdout
        assert "Traceback" not in stderr

    def test_tc_099_phase_command_case_insensitive(self):
        """
        TC-099: Phase Command - Case Insensitive Matching (UC-018 A3)

        Steps:
        1. /EXECUTE from PLAN -> transition succeeds.
        2. /Validate from EXECUTE -> transition succeeds.
        3. Headers reflect new phases.
        """
        test_input = _QUICK_CHAT + "/EXECUTE\n" + "/Validate\n" + "/menu\n" + "6\n"

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[INFO] Фаза изменена: PLAN -> EXECUTE" in stdout
        assert "[INFO] Фаза изменена: EXECUTE -> VALIDATE" in stdout
        assert "--- ЧАТ: Чат 1 [Фаза: VALIDATE] ---" in stdout
        assert "Неизвестная команда" not in stdout
        assert "Traceback" not in stderr

    def test_tc_100_phase_visible_in_header_and_info(self):
        """
        TC-100: Phase Visible In Header And /info (UC-018 A4)

        Steps:
        1. /execute then /menu -> phase changed before exiting the loop.
        2. Option 5 (return to chat) replays header with [Фаза: EXECUTE].
        3. /info shows 'Текущая фаза: EXECUTE'.
        """
        test_input = (
            _QUICK_CHAT
            + "/execute\n"
            + "/menu\n"
            + "5\n"  # Возврат в чат
            + "/info\n"
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Возврат в чат: Чат 1" in stdout
        replay = stdout.split("[OK] Возврат в чат: Чат 1", 1)[-1]
        assert "--- ЧАТ: Чат 1 [Фаза: EXECUTE] ---" in replay, (
            "Header replay must show the persisted phase (UC-018 A4)"
        )
        assert "Текущая фаза: EXECUTE" in replay
        assert "Traceback" not in stderr
