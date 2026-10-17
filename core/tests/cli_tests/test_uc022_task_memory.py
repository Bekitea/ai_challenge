"""E2E tests: TestUC022_TaskMemory.

UC-022: память задачи диалога (цель, ограничения, термины, уточнения).
Использует MockLlmProvider, сети не требует.
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import get_task_memory_by_name


class TestUC022_TaskMemory:
    """TC-142..TC-144: память задачи диалога (UC-022)."""

    def test_tc_142_task_memory_shown_in_info(self, monkeypatch):
        """TC-142: после обновления память задачи видна в /info."""
        monkeypatch.setenv("TASK_MEMORY_UPDATE_EVERY_N_MESSAGES", "1")
        test_input = (
            _QUICK_CHAT
            + "Расскажи о задаче\n"
            + "/info\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        memory = get_task_memory_by_name("Чат 1")
        assert memory is not None
        assert memory.goal == "уточнить детали проекта"
        assert memory.constraints == ["только Python", "без внешних API"]
        assert memory.terms == ["RAG — поиск по базе знаний"]

    def test_tc_143_no_task_memory_without_updates(self):
        """TC-143: до порога ходов память задачи в /info не отображается.

        Порог ``TASK_MEMORY_UPDATE_EVERY_N_MESSAGES`` управляет только
        внутридиалоговой каденцией. При выходе из чата память задачи
        извлекается и сохраняется всегда (финальный flush в
        ``Agent.save_memory``), поэтому проверяем оба факта: до выхода
        ``/info`` пуст, а ground truth после выхода уже содержит память —
        это ожидаемое, задокументированное в UC-022 поведение.
        """
        test_input = _QUICK_CHAT + "Привет\n" + "/info\n" + "/menu\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        assert "Память задачи:" not in stdout

        memory = get_task_memory_by_name("Чат 1")
        assert memory is not None
        assert memory.goal == "уточнить детали проекта"

    def test_tc_144_task_memory_persists_across_restarts(self, monkeypatch):
        """TC-144: память задачи сохраняется между запусками приложения.

        Чистота ветки по памяти задачи проверяется на уровне бизнес-логики
        (``test_task_memory.py::test_branch_does_not_copy_task_memory``). Сама
        ветка стартует с пустой памятью, но при выходе из чата память
        извлекается из скопированной истории — это финальный flush на выходе
        (UC-022), а не наследование памяти родителя.
        """
        monkeypatch.setenv("TASK_MEMORY_UPDATE_EVERY_N_MESSAGES", "1")
        # Создаём чат, наполняем память и выходим (память сохраняется на /menu)
        first = _QUICK_CHAT + "Поговорим о задаче\n" + "/menu\n8\n"
        run_cli_command(first)

        # Ground truth: память задачи сохранена на диск
        assert get_task_memory_by_name("Чат 1").goal == "уточнить детали проекта"

        # Возвращаемся в тот же чат и проверяем, что память на месте
        second = "2\n1\n/info\n/menu\n8\n"
        stdout, _, _ = run_cli_command(second)

        assert "Цель: уточнить детали проекта" in stdout
