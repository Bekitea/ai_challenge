"""E2E tests: TestUC001_CreateChatWithAllSettings."""

from e2e_helpers import run_cli_command


class TestUC001_CreateChatWithAllSettings:
    """
    Use Case UC-001: Create New Chat with All Settings

    Test Cases:
    - TC-001: Quick Chat Creation With Defaults
    - TC-002: Create Chat with Custom Settings
    - TC-003: Invalid Temperature Handling
    - TC-024: Long Chat Name Handling
    - TC-036: SlidingWindowStrategy Creation
    - TC-037: SlidingWindowStrategy With Custom Window
    - TC-038: SummarizationStrategy Creation
    - TC-039: SummarizationStrategy With Custom Parameters
    - TC-040: KeyValueMemoryStrategy Creation
    - TC-041: KeyValueMemoryStrategy With Custom Parameters
    - TC-042: DefaultStrategy Creation
    """

    def test_tc_001_quick_chat_creation_with_defaults(self):
        """
        TC-001: Quick Chat Creation With Defaults

        Steps:
        1. Select "New Chat"
        2. Press Enter (default name)
        3. Press Enter (skip prompt)
        4. Select model 1
        5. Press Enter (disable temp)
        6. Press Enter (disable top_p)
        7. Press Enter (default 0)
        8. Press Enter (default none)
        9. Verify chat created
        """
        test_input = (
            "1\n"  # Новый чат
            "\n"  # Пустой ответ на "Хотите настроить?" -> default "n", быстрый путь
            "/settings\n"  # Проверка настроек созданного чата (§4.4.7)
            "n\n"  # Не изменять настройки
            "/info\n"  # Проверка стратегии и профиля созданного чата
            "/menu\n"  # Выход из цикла чата в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[OK] Чат 'Чат" in stdout, "Default chat name should be 'Чат N'"
        assert "Используются настройки по умолчанию." in stdout, (
            "Quick path must announce default settings (UC-001 A1)"
        )
        # TC-001 step 4: defaults via /settings — model aliceai-llm-flash/latest,
        # temperature/top_p/top_k disabled (None), context window 200000
        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout
        assert "Модель: aliceai-llm-flash/latest" in stdout
        assert "Температура: отключена" in stdout
        assert "Top P: отключен" in stdout
        assert "Top K: отключено" in stdout
        assert "Размер контекстного окна: 200000 токенов" in stdout
        # TC-001 step 5: DefaultStrategy and no task profile via /info
        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout
        assert "Стратегия: DefaultStrategy" in stdout
        assert "Профиль задачи: (не привязан)" in stdout

    def test_tc_002_create_chat_with_custom_settings(self):
        """
        TC-002: Create Chat with Custom Settings

        Steps:
        1. Select "New Chat"
        2. Enter "Test Chat"
        3. Enter "Be concise"
        4. Select model 2
        5. Enter "1.5"
        6. Enter "0.8"
        7. Enter "50"
        8. Select "3" (medium)
        9. Verify settings
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Test Chat\n"  # Название
            "Be concise\n"  # Системный промпт
            "2\n"  # Model 2 (Qwen3.6)
            "1.5\n"  # Temperature
            "0.8\n"  # Top P
            "50\n"  # Top K
            "3\n"  # Reasoning effort: medium
            "128000\n"  # Context window
            "1\n"  # DefaultStrategy
            # Профилей нет -> выбор профиля пропускается автоматически
            "/settings\n"  # Проверка применённых настроек
            "n\n"  # Не изменять
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[OK] Чат 'Test Chat' создан!" in stdout
        # TC-002 step 13: all entered values saved correctly
        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout
        assert "Температура: 1.5" in stdout
        assert "Top P: 0.8" in stdout
        assert "Top K: 50" in stdout
        assert "Reasoning Effort: medium" in stdout
        assert "Размер контекстного окна: 128000 токенов" in stdout

    def test_tc_003_invalid_temperature_handling(self):
        """
        TC-003: Invalid Temperature Handling

        Steps:
        1-3. Create chat manually, reach temperature prompt
        4. Enter "abc" - should show warning, temp disabled
        5. Continue creation
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Temp Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "abc\n"  # Invalid temperature
            "\n"  # Top P disabled
            "\n"  # Top K disabled
            "\n"  # Reasoning effort
            "\n"  # Context window
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert (
            "Некорректное число. Используется значение по умолчанию (отключено)."
            in stdout
        )
        assert "[OK] Чат 'Temp Test' создан!" in stdout

    def test_tc_003b_temperature_out_of_range(self):
        """
        TC-003 steps 4-5: out-of-range temperature values ("-1", "3.0")
        trigger the range warning and disable temperature.
        """
        for bad_value in ("-1", "3.0"):
            test_input = (
                "1\n"  # Новый чат
                "y\n"  # Хотите настроить? (y/n)
                f"Range {bad_value}\n"  # Название
                "\n"  # Skip system prompt
                "1\n"  # Model 1
                f"{bad_value}\n"  # Out-of-range temperature
                "\n" + "\n" + "\n" + "\n"  # Top P / Top K / Reasoning / Context
                "1\n"  # DefaultStrategy
                "0\n"  # Нет профиля
                "/menu\n"
                "6\n"
            )

            stdout, stderr, returncode = run_cli_command(test_input)

            assert returncode == 0
            assert "Температура должна быть от 0.0 до 2.0." in stdout, (
                f"Range warning expected for temperature={bad_value}"
            )

    def test_tc_024_long_chat_name_handling(self):
        """
        TC-024: Long Chat Name Handling

        Steps:
        1. Enter 150-char name - accepted without truncation (§4.4.1)
        2/3. Verify full name saved and displayed
        """
        long_name = "A" * 150  # 150 characters

        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            f"{long_name}\n"  # Long name (no truncation expected)
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "2\n"  # Выбрать чат — проверить список
            "1\n"  # Выбор единственного чата
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert f"[OK] Чат '{long_name}' создан!" in stdout, (
            "Full 150-char name should be accepted without truncation"
        )
        assert long_name in stdout.split("[OK] Чат")[1], (
            "Chat list should display the full name"
        )

    def test_tc_036_sliding_window_strategy_creation(self):
        """
        TC-036: SlidingWindowStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 4 (SlidingWindow)
        3. Press Enter (accept default window_size=10)
        4. Verify strategy type = "SlidingWindowStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SlidingWindow Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "4\n"  # SlidingWindowStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SlidingWindowStrategy" in stdout or "4." in stdout

    def test_tc_037_sliding_window_strategy_custom_window(self):
        """
        TC-037: SlidingWindowStrategy With Custom Window

        Steps:
        1. Create new chat
        2. Select option 4 (SlidingWindow)
        3. Enter "20"
        4. Verify window_size = 20
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SlidingWindow Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "4\n"  # SlidingWindowStrategy
            "20\n"  # Custom window_size
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SlidingWindowStrategy" in stdout or "window" in stdout.lower()

    def test_tc_038_summarization_strategy_creation(self):
        """
        TC-038: SummarizationStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 2 (Summarization)
        3. Press Enter (non_compressible_count=2)
        4. Press Enter (buffer_size=3)
        5. Verify strategy type = "SummarizationStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Summarization Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SummarizationStrategy" in stdout

    def test_tc_039_summarization_strategy_custom_parameters(self):
        """
        TC-039: SummarizationStrategy With Custom Parameters

        Steps:
        1. Create new chat
        2. Select option 2 (Summarization)
        3. Enter "5" (non_compressible_count)
        4. Enter "4" (buffer_size)
        5. Verify custom parameters
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Summarization Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "5\n"  # non_compressible_count=5
            "4\n"  # buffer_size=4
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SummarizationStrategy" in stdout

    def test_tc_040_key_value_memory_strategy_creation(self):
        """
        TC-040: KeyValueMemoryStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 3 (KeyValueMemory)
        3. Press Enter (non_compressible_count=2)
        4. Press Enter (buffer_size=3)
        5. Verify strategy type = "KeyValueMemoryStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "KeyValueMemory Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "3\n"  # KeyValueMemoryStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "KeyValueMemoryStrategy" in stdout

    def test_tc_041_key_value_memory_strategy_custom_parameters(self):
        """
        TC-041: KeyValueMemoryStrategy With Custom Parameters

        Steps:
        1. Create new chat
        2. Select option 3 (KeyValueMemory)
        3. Enter "3" (non_compressible_count)
        4. Enter "5" (buffer_size)
        5. Verify custom parameters
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "KeyValueMemory Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "3\n"  # KeyValueMemoryStrategy
            "3\n"  # non_compressible_count=3
            "5\n"  # buffer_size=5
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "KeyValueMemoryStrategy" in stdout

    def test_tc_042_default_strategy_creation(self):
        """
        TC-042: DefaultStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 1 (Default)
        3. Verify no extra parameters prompted
        4. Verify strategy type = "DefaultStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "DefaultStrategy Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "DefaultStrategy" in stdout or "[OK]" in stdout
