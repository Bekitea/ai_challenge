"""E2E tests: TestUC001_CreateChatWithAllSettings."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_last_agent, get_settings, get_strategy


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
        2. Press Enter (default "n" -> quick path)
        3. Select model 3 (Alice AI LLM Flash)
        4. Press Enter (reasoning effort default "none")
        5. Verify chat created and default settings
        """
        test_input = (
            "1\n"  # Новый чат
            "\n"  # Пустой ответ на "Хотите настроить?" -> default "n", быстрый путь
            "3\n"  # Модель: Alice AI LLM Flash (yandex)
            "\n"  # Reasoning effort: default "none"
            "/settings\n"  # Проверка настроек созданного чата
            "n\n"  # Не изменять настройки
            "/info\n"  # Проверка стратегии и профиля созданного чата
            "/menu\n"  # Выход из цикла чата в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # UI-only: quick-path announcement and section headers
        assert "Используются настройки по умолчанию." in stdout, (
            "Quick path must announce default settings (UC-001 A1)"
        )
        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout
        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout

        # TC-001: defaults persisted — model aliceai-llm-flash/latest,
        # reasoning effort "none", temperature/top_p/top_k disabled (None),
        # context window 200000, DefaultStrategy, no task profile
        agent = get_last_agent()
        assert agent["name"].startswith("Чат"), "Default chat name should be 'Чат N'"
        settings = get_settings(agent)
        assert settings["model_id"] == "aliceai-llm-flash/latest"
        assert settings["reasoning_effort"] == "none"
        assert settings.get("temperature") is None
        assert settings.get("top_p") is None
        assert settings.get("top_k") is None
        assert settings.get("max_tokens") is None
        assert settings["context_window_size"] == 200_000
        assert get_strategy(agent)["strategy_type"] == "DefaultStrategy"
        assert agent["task_profile_id"] is None

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
            "512\n"  # Max Tokens
            "3\n"  # Reasoning effort: medium
            "128000\n"  # Context window
            "1\n"  # DefaultStrategy
            # Профилей нет -> выбор профиля пропускается автоматически
            "/settings\n"  # Проверка применённых настроек
            "n\n"  # Не изменять
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout
        # TC-002 step 13: all entered values saved correctly
        settings = get_settings(get_agent_by_name("Test Chat"))
        assert settings["model_id"] == "qwen3.6-35b-a3b/latest"
        assert settings["temperature"] == 1.5
        assert settings["top_p"] == 0.8
        assert settings["top_k"] == 50
        assert settings["max_tokens"] == 512
        assert settings["reasoning_effort"] == "medium"
        assert settings["context_window_size"] == 128_000

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
            "\n"  # Max Tokens (без ограничений)
            "\n"  # Reasoning effort
            "\n"  # Context window
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert (
            "Некорректное число. Используется значение по умолчанию (отключено)."
            in stdout
        )
        settings = get_settings(get_agent_by_name("Temp Test"))
        assert settings.get("temperature") is None

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
                "\n" + "\n" + "\n" + "\n" + "\n"  # Top P / Top K / Max Tokens / Reasoning / Context
                "1\n"  # DefaultStrategy
                "0\n"  # Нет профиля
                "/menu\n"
                "8\n"
            )

            stdout, _, _ = run_cli_command(test_input)

            assert "Температура должна быть от 0.0 до 2.0." in stdout, (
                f"Range warning expected for temperature={bad_value}"
            )
            settings = get_settings(get_agent_by_name(f"Range {bad_value}"))
            assert settings.get("temperature") is None

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "2\n"  # Выбрать чат — проверить список
            "1\n"  # Выбор единственного чата
            "/menu\n"
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # Chat list was rendered and the full name persisted without truncation
        assert "--- ВАШИ ЧАТЫ ---" in stdout
        agent = get_agent_by_name(long_name)
        assert agent is not None, "Full 150-char name should be accepted without truncation"
        assert agent["name"] == long_name

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "4\n"  # SlidingWindowStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("SlidingWindow Test"))
        assert strategy["strategy_type"] == "SlidingWindowStrategy"
        assert strategy["window_size"] == 10

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "4\n"  # SlidingWindowStrategy
            "20\n"  # Custom window_size
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("SlidingWindow Custom"))
        assert strategy["strategy_type"] == "SlidingWindowStrategy"
        assert strategy["window_size"] == 20

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "2\n"  # SummarizationStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("Summarization Test"))
        assert strategy["strategy_type"] == "SummarizationStrategy"
        assert strategy["non_compressible_count"] == 2
        assert strategy["buffer_size"] == 3

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "2\n"  # SummarizationStrategy
            "5\n"  # non_compressible_count=5
            "4\n"  # buffer_size=4
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("Summarization Custom"))
        assert strategy["strategy_type"] == "SummarizationStrategy"
        assert strategy["non_compressible_count"] == 5
        assert strategy["buffer_size"] == 4

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "3\n"  # KeyValueMemoryStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("KeyValueMemory Test"))
        assert strategy["strategy_type"] == "KeyValueMemoryStrategy"
        assert strategy["non_compressible_count"] == 2
        assert strategy["buffer_size"] == 3

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "3\n"  # KeyValueMemoryStrategy
            "3\n"  # non_compressible_count=3
            "5\n"  # buffer_size=5
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("KeyValueMemory Custom"))
        assert strategy["strategy_type"] == "KeyValueMemoryStrategy"
        assert strategy["non_compressible_count"] == 3
        assert strategy["buffer_size"] == 5

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
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "0\n"  # Нет профиля задачи
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        run_cli_command(test_input)

        strategy = get_strategy(get_agent_by_name("DefaultStrategy Test"))
        assert strategy["strategy_type"] == "DefaultStrategy"
        assert "window_size" not in strategy
        assert "buffer_size" not in strategy
