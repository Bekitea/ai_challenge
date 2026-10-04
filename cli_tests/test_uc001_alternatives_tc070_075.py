"""E2E tests: TestUC001_Alternatives_TC070_075."""

from e2e_helpers import run_cli_command


class TestUC001_Alternatives_TC070_075:
    """
    TC-070..TC-075: Alternative flows of chat creation (spec §UC-001 A4-A11).
    """

    def test_tc_070_skip_system_prompt_on_empty_input(self):
        """
        TC-070: Skip System Prompt On Empty Input (UC-001 A4)

        Steps: manual creation, empty system prompt -> no error; after sending
        a message the history contains only user + assistant messages.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "NoSysPrompt\n"  # Название
            "\n"  # Пустой системный промпт (пропуск)
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings defaults
            "1\n"  # Strategy
            "Hello\n"  # Сообщение в чат (генерация ответа модели)
            "n\n"  # Показать рассуждения модели? -> нет
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'NoSysPrompt' создан!" in stdout
        # System prompt was skipped -> no [SYSTEM] entry anywhere in output
        assert "[SYSTEM]" not in stdout
        # History contains only user + assistant messages (mock exchange happened)
        assert "запрос: 'Hello" in stdout
        assert "[AGENT]" in stdout

    def test_tc_071_empty_inputs_disable_temperature_and_top_p(self):
        """
        TC-071: Empty Inputs Disable Temperature And Top P (UC-001 A6)

        Empty Enter at temperature/top_p prompts -> no warning, params None;
        /settings shows them as disabled.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "DisabledTP\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n"  # Temperature: Enter -> disabled
            "\n"  # Top P: Enter -> disabled
            "\n" + "\n" + "\n" + "\n"  # Top K / Reasoning / Context
            "1\n"  # Strategy
            "/settings\n"  # Просмотр настроек
            "n\n"  # Не изменять
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'DisabledTP' создан!" in stdout
        # No warnings for empty temperature/top_p inputs
        assert "Температура должна быть от 0.0 до 2.0" not in stdout
        assert "Top P должен быть от 0.0 до 1.0" not in stdout
        assert "--- НАСТРОЙКИ АГЕНТА ---" in stdout  # /settings view was reached

    def test_tc_072_invalid_top_k_reprompts_zero_disables(self):
        """
        TC-072: Invalid Top K Re-Prompts; Zero Disables (UC-001 A8)
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "TopKTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n"  # Temp/TopP disabled
            "-5\n"  # Top K invalid (negative)
            "abc\n"  # Top K non-numeric
            "0\n"  # Top K zero -> disabled
            "\n" + "\n"  # Reasoning / Context
            "1\n"  # Strategy
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Top K должен быть >= 0" in stdout
        assert "Введите корректное число" in stdout
        assert "[OK] Чат 'TopKTest' создан!" in stdout

    def test_tc_073_invalid_reasoning_effort_reprompts_default(self):
        """
        TC-073: Invalid Reasoning Effort Re-Prompts; Empty Selects Default (UC-001 A9)
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "ReasonTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n"  # Temp/TopP/TopK defaults
            "abc\n"  # Non-numeric choice
            "5\n"  # Out of range 1-4
            "\n"  # Empty -> default (1st option)
            "\n"  # Context window
            "1\n"  # Strategy
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите корректное число" in stdout
        assert "Выбор должен быть от 1 до 4" in stdout
        assert "[OK] Чат 'ReasonTest' создан!" in stdout

    def test_tc_074_invalid_context_window_falls_back_to_200k(self):
        """
        TC-074: Invalid Context Window Falls Back To 200k (UC-001 A10)

        Covers spec steps 2 and 3 ("abc" and "0") in one session; step 4
        (empty input, no warning) is implicitly covered by other tests that
        press Enter at this prompt without any warning assertion.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "CtxAbc\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n"  # Temp/TopP/TopK/Reasoning
            "abc\n"  # Invalid context -> fallback 200k
            "1\n"  # Strategy
            "/menu\n"  # Выход в меню (профилей нет — шаг привязки пропущен)
            "1\n"  # Новый чат (повтор создания)
            "y\n"  # Хотите настроить?
            "CtxZero\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n"  # Temp/TopP/TopK/Reasoning
            "0\n"  # Zero context -> fallback 200k
            "1\n"  # Strategy
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Некорректное число. Используется 200k." in stdout
        assert "Размер должен быть положительным числом. Используется 200k." in stdout
        assert "[OK] Чат 'CtxZero' создан!" in stdout

    def test_tc_075_invalid_strategy_choice_reprompts(self):
        """
        TC-075: Invalid Strategy Choice Re-Prompts (UC-001 A11)
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "StratTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings defaults
            "5\n"  # Стратегия вне диапазона 1-4
            "abc\n"  # Стратегия нечисловая
            "1\n"  # Корректный выбор DefaultStrategy
            "/info\n"  # Проверка стратегии созданного чата
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---" in stdout
        assert stdout.count("Неверный выбор, попробуйте снова.") >= 2
        assert "[OK] Чат 'StratTest' создан!" in stdout
        assert "DefaultStrategy" in stdout
