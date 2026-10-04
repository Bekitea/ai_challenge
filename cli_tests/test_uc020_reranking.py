"""E2E tests: TestUC020_Reranking.

UC-020: per-chat управление реранкингом командой ``/rerank on|off``.

В тестовом режиме (``APPLICATION_MODE=TEST``) используется
``MockRerankerProvider``, поэтому Ollama/сервис реранкинга не требуются.
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command


class TestUC020_Reranking:
    """TC-135..TC-138: переключатель реранкинга (UC-020)."""

    def test_tc_135_reranking_enabled_by_default(self):
        """TC-135: по умолчанию реранкинг включён."""
        test_input = _QUICK_CHAT + "/rerank\n" + "/menu\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[INFO] Реранкинг: включён." in stdout

    def test_tc_136_toggle_reranking(self):
        """TC-136: /rerank off и /rerank on переключают состояние."""
        test_input = (
            _QUICK_CHAT
            + "/rerank off\n"
            + "/rerank\n"
            + "/rerank on\n"
            + "/rerank\n"
            + "/menu\n6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[OK] Реранкинг отключён." in stdout
        assert "[INFO] Реранкинг: отключён." in stdout
        assert "[OK] Реранкинг включён." in stdout
        assert "[INFO] Реранкинг: включён." in stdout

    def test_tc_137_reranking_invalid_argument(self):
        """TC-137: неверный аргумент -> подсказка по использованию."""
        test_input = _QUICK_CHAT + "/rerank maybe\n" + "/menu\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[WARN] Использование: /rerank on|off" in stdout

    def test_tc_138_reranking_state_in_rag_menu(self):
        """TC-138: состояние реранкинга показывается в меню /rag."""
        test_input = (
            _QUICK_CHAT
            + "/rerank off\n"
            + "/rag\n0\n"
            + "/menu\n6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- БАЗЫ ЗНАНИЙ ЧАТА:" in stdout
        assert "[INFO] Реранкинг: отключён." in stdout
