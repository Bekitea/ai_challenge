"""E2E tests: TestUC004_TC078_083_MessagingBranches."""

from e2e_helpers import _QUICK_CHAT, _manual_chat, run_cli_command


class TestUC004_TC078_083_MessagingBranches:
    """TC-078..TC-083: Message exchange branches (UC-004 A4, A5, A6, A8, A9)."""

    def test_tc_078_token_statistics_lines_after_response(self):
        """
        TC-078: Token Statistics Lines After Response (UC-004 steps 4-11)

        Mock provider always reports prompt_tokens=100, completion_tokens=50;
        default context window is 200000 -> fill percent 0.1%.
        """
        test_input = (
            _QUICK_CHAT + "Hello agent\n"
            "\n"  # Отказ показать рассуждения
            "/info\n"
            "/menu\n"
            "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[AGENT] печатает..." in stdout
        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "[Токены: prompt: 100, completion: 50]" in stdout
        assert "[Заполненность контекста: 100/200000 (0.1%)]" in stdout
        # Шаг 5: история обновлена — /info показывает счётчик сообщений
        assert "Сообщений: 2" in stdout

    def test_tc_079_context_window_exceeded_error(self):
        """
        TC-079: Context Window Exceeded Error (UC-004 A4)

        Create a chat with context window = 1 token; the mock response always
        reports prompt_tokens=100 > 1, so the first message triggers
        ContextWindowExceededError.
        """
        test_input = (
            "1\n"
            + "y\n"
            + "TinyCtx\n"
            + "\n"  # Системный промпт
            + "\n"  # Модель
            + "\n"  # temp
            + "\n"  # top_p
            + "\n"  # top_k
            + "\n"  # reasoning
            + "1\n"  # Context window = 1 токен
            + "1\n"  # DefaultStrategy
            + "0\n"  # Профиль
            + "trigger overflow\n"  # Сообщение -> превышение окна
            + "5\n"  # Вернуться в чат (шаг 4) — чат остаётся активным
            + "/info\n"
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Превышен лимит контекстного окна:" in stdout
        assert "(лимит: 1)" in stdout
        assert "Необходимо очистить историю сообщений или создать новый чат." in stdout
        # Шаг 3: возврат в главное меню
        assert "Ваш выбор (1-6):" in stdout
        # Шаг 4: тот же чат всё ещё активен и доступен через опцию 5
        assert "[OK] Возврат в чат: TinyCtx" in stdout
        assert "Traceback" not in stderr

    def test_tc_080_backend_error_during_message_exchange(self):
        """
        TC-080: Backend Error During Message Exchange (UC-004 A5)

        TEST_MOCK_RAISE_GENERIC=1 makes the mock provider raise an arbitrary
        RuntimeError on generation.
        """
        test_input = (
            _QUICK_CHAT + "cause failure\n"
            "6\n"  # Выход из меню (чат-луп завершится на ошибке)
        )

        stdout, stderr, returncode = run_cli_command(
            test_input, extra_env={"TEST_MOCK_RAISE_GENERIC": "1"}
        )

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Ошибка: Mock backend failure (TEST)" in stdout
        # Шаг 3: цикл чата покинут, показано главное меню
        after_error = stdout.split("[ERROR] Ошибка:", 1)[-1]
        assert "Ваш выбор (1-6):" in after_error or "До свидания!" in after_error
        assert "Traceback" not in stderr

    def test_tc_081_keyboard_interrupt_during_exchange(self):
        """
        TC-081: Keyboard Interrupt During Exchange (UC-004 A6)

        Ctrl+C cannot be injected through piped stdin; EOF at the chat input
        prompt exercises the identical loop-exit path (guide §Testing
        Limitations). The dedicated KeyboardInterrupt branch prints
        'Прервано пользователем.' — its sibling coverage lives in TC-086.
        """
        test_input = (
            _QUICK_CHAT + "first message\n\n"  # отказ от рассуждений
            # EOF прямо на промпте ввода чата (эмуляция Ctrl+C на пустом вводе)
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[AGENT]:" in stdout, "First exchange must complete before EOF"
        # Цикл чата покинут без падения; приложение завершилось корректно
        assert "Traceback" not in stderr
        assert "EOFError" not in stderr

    def test_tc_082_long_response_wrapping(self):
        """
        TC-082: Long Response Wrapping (UC-004 A8)

        A long user message yields a long mock response line; the app must
        print it without crash or garbling.
        """
        long_msg = "L" * 3000
        test_input = (
            _QUICK_CHAT + long_msg + "\n"
            "\n"  # отказ от рассуждений
            "/menu\n"
            "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        agent_lines = [ln for ln in stdout.splitlines() if ln.startswith("[AGENT]:")]
        assert agent_lines, "Response must be printed"
        # Строка ответа целая: содержит маркер mock-ответа без разрывов
        assert any("[MOCK RESPONSE]" in ln for ln in agent_lines), (
            "Response line must not be broken/garbled"
        )
        assert "Traceback" not in stderr

    def test_tc_083_reasoning_display_prompt(self):
        """
        TC-083: Reasoning Display Prompt (UC-004 A9)

        Mock provider always attaches reasoning content. Entering 'y' prints
        the [Reasoning] block; entering 'n' prints nothing.
        """
        test_input = (
            _manual_chat("ReasonChat")
            + "hello one\n"
            + "y\n"  # Показать рассуждения
            + "hello two\n"
            + "n\n"  # Не показывать рассуждения
            + "/menu\n"
            + "6\n"
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Показать рассуждения модели? (y/n):" in stdout
        assert "[Reasoning]:" in stdout
        assert "[MOCK REASONING]" in stdout
        # Второй обмен с 'n' не печатает блок рассуждений повторно
        after_second = stdout.split("hello two", 1)[-1]
        assert "[Reasoning]:" not in after_second
        assert "Traceback" not in stderr
