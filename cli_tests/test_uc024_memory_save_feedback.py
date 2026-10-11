"""E2E tests: TestUC024_MemorySaveFeedback.

UC-024: индикация заполнения глобальной и профильной памяти (начало,
время выполнения, ошибка; по каждому чату при старте приложения).
Использует MockLlmProvider, сети не требует.
"""

from e2e_helpers import _QUICK_CHAT, _manual_chat, run_cli_command


class TestUC024_MemorySaveFeedback:
    """TC-146, TC-147: индикация сохранения памяти (UC-024)."""

    def test_tc_146_memory_save_feedback_on_chat_exit(self):
        """TC-146: при выходе из чата видно начало, конец и время сохранения."""
        test_input = _QUICK_CHAT + "Привет\n\n" + "/menu\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "Возврат в меню..." in stdout
        assert "[INFO] Сохранение памяти чата '" in stdout
        assert "сохранена за" in stdout
        assert "[OK] Память чата '" in stdout

    def test_tc_147_memory_save_feedback_on_start_per_chat(self):
        """TC-147: при старте видно начало и результат по каждому чату."""
        # Создаём два чата и выходим из них через /stop (память не сохраняется),
        # затем закрываем приложение.
        first_run = (
            _manual_chat("Chat A")
            + "Привет\n\n"
            + "/stop\n"
            + _manual_chat("Chat B")
            + "Привет\n\n"
            + "/stop\n"
            + "6\n"
        )
        run_cli_command(first_run)

        # Второй запуск: save_unsaved_memories подхватывает несохранённые чаты.
        stdout, _, _ = run_cli_command("6\n")

        assert "[INFO] Проверка несохранённой памяти..." in stdout
        assert "[INFO] Сохранение памяти чата 'Chat A'..." in stdout
        assert "[INFO] Сохранение памяти чата 'Chat B'..." in stdout
        assert "[OK] 'Chat A': сохранено за" in stdout
        assert "[OK] 'Chat B': сохранено за" in stdout

    def test_tc_148_empty_chat_is_not_unsaved_memory(self):
        """TC-148: чат без сообщений не считается несохранённой памятью."""
        # Создаём чат и сразу выходим из цикла чата через /stop, сообщений нет.
        first_run = _QUICK_CHAT + "/stop\n6\n"
        run_cli_command(first_run)

        stdout, _, _ = run_cli_command("6\n")

        assert "[INFO] Проверка несохранённой памяти..." in stdout
        assert "[INFO] Несохранённой памяти нет." in stdout
        assert "Сохранение памяти чата '" not in stdout
