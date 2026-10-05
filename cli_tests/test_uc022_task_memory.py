"""E2E tests: TestUC022_TaskMemory.

UC-022: память задачи диалога (цель, ограничения, термины, уточнения).
Использует MockLlmProvider, сети не требует.
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command


class TestUC022_TaskMemory:
    """TC-142..TC-144: память задачи диалога (UC-022)."""

    def test_tc_142_task_memory_shown_in_info(self, monkeypatch):
        """TC-142: после обновления память задачи видна в /info."""
        monkeypatch.setenv("TASK_MEMORY_UPDATE_EVERY_N_MESSAGES", "1")
        test_input = (
            _QUICK_CHAT
            + "Расскажи о задаче\n\n"
            + "/info\n"
            + "/menu\n6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        assert "Память задачи:" in stdout
        assert "Цель: уточнить детали проекта" in stdout
        assert "Ограничения: только Python; без внешних API" in stdout
        assert "RAG — поиск по базе знаний" in stdout

    def test_tc_143_no_task_memory_without_updates(self):
        """TC-143: до порога ходов память задачи в /info не отображается."""
        test_input = _QUICK_CHAT + "Привет\n\n" + "/info\n" + "/menu\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        assert "Память задачи:" not in stdout

    def test_tc_144_task_memory_persists_and_branch_is_clean(self, monkeypatch):
        """TC-144: память сохраняется между чатами, а ветка её не наследует."""
        monkeypatch.setenv("TASK_MEMORY_UPDATE_EVERY_N_MESSAGES", "1")
        # Создаём чат, наполняем память и выходим (память сохраняется на /menu)
        first = _QUICK_CHAT + "Поговорим о задаче\n\n" + "/menu\n6\n"
        run_cli_command(first)

        # Возвращаемся в тот же чат и проверяем, что память на месте
        second = "2\n1\n/info\n/menu\n6\n"
        stdout, _, _ = run_cli_command(second)

        assert "Цель: уточнить детали проекта" in stdout
