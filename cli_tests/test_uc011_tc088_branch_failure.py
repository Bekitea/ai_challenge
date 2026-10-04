"""E2E tests: TestUC011_TC088_BranchFailure."""

from e2e_helpers import _manual_chat, run_cli_command


class TestUC011_TC088_BranchFailure:
    """TC-088: Branch Creation Backend Error (UC-011 A3)."""

    def test_tc_088_branch_creation_backend_error(self):
        """
        TC-088: Branch Creation Backend Error (UC-011 A3)

        TEST_FAIL_CREATE_BRANCH=1 raises right after the branch is created
        but BEFORE current_agent switches. Expected: '[ERROR] Ошибка при
        создании ветки: {e}', no switch — subsequent /info shows the original
        chat name.
        """
        test_input = (
            _manual_chat("OrigChat")
            + "/branch\n"
            + "FailBranch\n"  # Название ветки
            + "/info\n"  # Текущий агент не переключился
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(
            test_input, extra_env={"TEST_FAIL_CREATE_BRANCH": "1"}
        )

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Ошибка при создании ветки: Mock branch failure (TEST)" in stdout
        # Шаг 3: возврата в цикл не произошло, current_agent — исходный чат
        info_section = stdout.split("--- ИНФОРМАЦИЯ О ЧАТЕ ---", 1)[-1]
        assert "Название: OrigChat" in info_section
        assert "Название: FailBranch" not in info_section
        assert "Traceback" not in stderr
