"""E2E tests: TestUC001_TC004_008_CreationValidation."""

from e2e_helpers import run_cli_command
from ground_truth import (
    get_agent_by_name,
    get_agents,
    get_last_agent,
    get_settings,
    get_strategy,
)


class TestUC001_TC004_008_CreationValidation:
    """
    TC-004..TC-006, TC-008: Validation branches of the chat creation flow
    (UC-001 A2, A3, A5, A12). TC-007 уже покрыт в основном файле.
    """

    def test_tc_004_invalid_answer_to_configure_prompt(self):
        """
        TC-004: Invalid Answer To Configure Prompt (UC-001 A2)

        Steps:
        1. Select option 1 -> configure prompt displayed.
        2. Enter "maybe" -> warning + same question re-prompted.
        3. Enter "да" -> accepted as affirmative, manual path starts.
        """
        test_input = (
            "1\n"  # Новый чат
            + "maybe\n"  # Некорректный ответ на "Хотите настроить?"
            + "да\n"  # Русская аффирмация принимается (§4.4.0)
            + "TC004 Chat\n"  # Название (ручной путь стартовал)
            + "\n"  # Системный промпт
            + "1\n"  # Модель
            + "\n" * 6  # Дефолтные настройки
            + "1\n"  # DefaultStrategy
            + "0\n"  # Профиль не привязывать
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Хотите настроить чат? (y/n, по умолчанию n):" in stdout
        assert "Введите 'y' (да) или 'n' (нет)" in stdout, (
            "'maybe' must produce the invalid-answer warning (UC-001 A2)"
        )
        assert "Введите название чата" in stdout, (
            "'да' must be accepted and start the manual path (§4.4.0)"
        )
        assert get_agent_by_name("TC004 Chat") is not None

    def test_tc_005_default_chat_name_on_empty_input(self):
        """
        TC-005: Default Chat Name On Empty Input (UC-001 A3)

        Steps:
        1. Ensure exactly 2 chats exist (two quick chats).
        2. Start manual creation, press Enter at the name prompt.
        3. Complete creation -> [OK] Чат 'Чат 3' создан!
        4. Verify chat list contains 'Чат 3'.
        """
        test_input = (
            "1\n\n3\n\n/menu\n"  # Чат 1 (быстрый путь: модель + reasoning)
            + "1\n\n3\n\n/menu\n"  # Чат 2 (быстрый путь: модель + reasoning)
            + "1\n"  # Новый чат
            + "y\n"  # Ручная настройка
            + "\n"  # Пустое имя -> default 'Чат N' (N = 2 + 1 = 3)
            + "\n"  # Системный промпт
            + "1\n"  # Модель
            + "\n" * 6  # Дефолтные настройки
            + "1\n"  # DefaultStrategy
            + "0\n"  # Профиль не привязывать
            + "/menu\n"
            + "2\n"  # Список чатов (шаг 4), затем EOF закрывает приложение
        )
        stdout, _, _ = run_cli_command(test_input)

        # Шаг 3: пустое имя -> default 'Чат 3' (2 существующих + 1)
        assert [a["name"] for a in get_agents()] == ["Чат 1", "Чат 2", "Чат 3"]
        assert get_last_agent()["name"] == "Чат 3"
        # Шаг 4: список чатов отрисован
        assert "--- ВАШИ ЧАТЫ ---" in stdout

    def test_tc_006_out_of_range_model_selection_reprompts(self):
        """
        TC-006: Out-Of-Range Model Selection Re-Prompts (UC-001 A5)

        Steps:
        1. Start manual creation, pass name/system prompt.
        2. Enter "9" -> 'Неверный выбор, попробуйте снова.' + re-prompt.
        3. Enter "abc" -> same warning + re-prompt again.
        4. Enter "3" -> Alice AI LLM Flash selected, temperature prompt shown.
        """
        test_input = (
            "1\n"
            + "y\n"
            + "TC006\n"
            + "\n"  # Системный промпт
            + "9\n"  # Вне диапазона
            + "abc\n"  # Нечисловой ввод
            + "3\n"  # Alice AI LLM Flash (yandex)
            + "\n"  # Температура
            + "\n"  # Top P
            + "\n"  # Top K
            + "\n"  # Max Tokens
            + "\n"  # Reasoning effort
            + "\n"  # Context window
            + "1\n"  # DefaultStrategy
            # Профиля нет -> '(нет доступных профилей)', блок привязки
            # завершается без ввода; сразу переходим в цикл чата.
            + "/settings\n"  # Проверить выбранную модель
            + "n\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- НАСТРОЙКИ АГЕНТА ---" in stdout
        assert stdout.count("Неверный выбор, попробуйте снова.") >= 2, (
            "'9' and 'abc' must each re-prompt the model selection (UC-001 A5)"
        )
        assert "Температура (0.0 - 2.0, Enter для отключения):" in stdout
        assert "(нет доступных профилей)" in stdout
        assert get_settings(get_agent_by_name("TC006"))["model_id"] == (
            "aliceai-llm-flash/latest"
        )

    def test_tc_008_non_integer_strategy_param_repeats_selection(self):
        """
        TC-008: Non-Integer Strategy Parameter Repeats Strategy Selection
        (UC-001 A12)

        Steps:
        1. Reach strategy selection block.
        2. Select "2" (SummarizationStrategy) -> non-compressible prompt shown.
        3. Enter "abc" -> 'Ошибка: {e}. Попробуйте снова.'; the whole strategy
           selection repeats.
        4. Select "2", enter valid integers -> SummarizationStrategy created.
        """
        test_input = (
            "1\n"
            + "y\n"
            + "TC008\n"
            + "\n"  # Системный промпт
            + "1\n"  # Модель
            + "\n" * 6  # Дефолтные настройки
            + "2\n"  # SummarizationStrategy
            + "abc\n"  # Некорректное число несжимаемых сообщений
            + "2\n"  # Повтор выбора стратегии
            + "3\n"  # Несжимаемые сообщения
            + "4\n"  # Размер буфера
            # Профилей нет => блок привязки профиля пропускается без ввода.
            + "/info\n"  # Проверка стратегии и параметров
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Количество несжимаемых сообщений (по умолчанию 2):" in stdout
        assert (
            "Ошибка: invalid literal for int() with base 10: 'abc'. Попробуйте снова."
            in (stdout)
        ), "ValueError text must be interpolated into the repeated-selection error"
        # Блок стратегии выводится повторно (весь цикл выбора)
        assert stdout.count("--- ВЫБОР СТРАТЕГИИ УПРАВЛЕНИЯ КОНТЕКСТНЫМ ОКНОМ ---") >= 2
        strategy = get_strategy(get_agent_by_name("TC008"))
        assert strategy["strategy_type"] == "SummarizationStrategy"
        assert strategy["non_compressible_count"] == 3
        assert strategy["buffer_size"] == 4
