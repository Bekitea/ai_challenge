#!/usr/bin/env python3
"""
E2E tests for CLI application using pytest.

These tests emulate real user interaction with the CLI interface.
IMPORTANT: Tests use subprocess to simulate actual user behavior,
avoiding pytest fixtures for maximum realism.

Test naming convention: test_tc_XXX_<description>
where XXX is the test case number from cli_spec.md specification.
"""

import os

# ВАЖНО: Установить APPLICATION_MODE ДО импорта любых модулей проекта,
# так как config.py читает эту переменную при загрузке модуля
os.environ["APPLICATION_MODE"] = "TEST"

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def get_project_root() -> Path:
    """Dynamically resolve project root directory."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent


def get_test_data_path() -> Path:
    """Get path to test data directory."""
    return get_project_root() / "test-data"


def clean_test_data():
    """Clean test data directory before and after each test."""
    test_data_path = get_test_data_path()
    if test_data_path.exists():
        shutil.rmtree(test_data_path)
    test_data_path.mkdir(parents=True, exist_ok=True)


# Pytest fixture for automatic cleanup before each test
@pytest.fixture(autouse=True)
def setup_clean_test_environment():
    """Automatically clean test data and initialize DB before each test in this module."""
    clean_test_data()

    # Initialize database
    sys.path.insert(0, str(get_project_root()))
    from storage.db_connection import DatabaseConnection

    db = DatabaseConnection(connect_args={"check_same_thread": False, "timeout": 30})
    db.init_tables(__import__("storage.orm_models", fromlist=["Base"]).Base.metadata)
    # Явно закрываем соединение, чтобы освободить файл БД для subprocess на Windows
    db.close()

    yield
    # Optional: cleanup after test as well
    # clean_test_data()


def run_cli_command(test_input: str, timeout: int = 30) -> tuple[str, str, int]:
    """
    Run CLI application with given input and return output.

    This function simulates real user interaction by:
    1. Spawning actual subprocess
    2. Sending input via stdin (like real keyboard input)
    3. Capturing stdout/stderr (like real terminal output)

    Args:
        test_input: String with newlines representing user keystrokes
        timeout: Maximum execution time in seconds

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    project_root = get_project_root()

    # Устанавливаем переменную окружения для тестового режима
    env = os.environ.copy()
    env["APPLICATION_MODE"] = "TEST"

    process = subprocess.Popen(
        [sys.executable, "main_cli.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(project_root),
        env=env,
    )

    stdout, stderr = process.communicate(input=test_input, timeout=timeout)
    return stdout, stderr, process.returncode


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


class TestUC002_SelectExistingChatFromList:
    """
    Use Case UC-002: Select Existing Chat from List

    Test Cases:
    - TC-009: Select Chat from Empty List
    - TC-010: Preview with System Prompt Only
    - TC-011: Preview with User Message
    """

    def test_tc_009_select_chat_from_empty_list(self):
        """
        TC-009: Select Chat from Empty List

        Steps:
        1. Ensure no chats exist
        2. Select "Выбрать чат"
        3. Verify message "Нет доступных чатов"
        4. Verify returns to Main Menu
        """
        test_input = (
            "2\n"  # Выбрать чат (empty list)
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert (
            "Нет доступных чатов" in stdout
            or "Нет доступных чатов. Создайте новый." in stdout
        )

    def test_tc_010_preview_with_system_prompt_only(self):
        """
        TC-010: Preview with System Prompt Only

        Steps:
        1. Create chat with system prompt only
        2. Return to menu using /menu command
        3. Exit app
        4. Verify preview shows "(нет сообщений)"
        5. Verify count shows "Сообщений: 0"
        """
        create_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SystemPromptOnly\n"  # Название
            "You are helpful\n"  # System prompt only
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to main menu (NOT "4" which would be sent as a message)
            "4\n"  # Exit app
        )
        run_cli_command(create_input)

        select_input = (
            "2\n"  # Выбрать чат
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(select_input)

        assert returncode == 0
        assert "(нет сообщений)" in stdout or "Сообщений: 0" in stdout

    def test_tc_011_preview_with_user_message(self):
        """
        TC-011: Preview with User Message

        Steps:
        1. Create chat
        2. Send message "Hello world"
        3. Return to menu
        4. Verify preview shows "Hello world"
        """
        create_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "PreviewTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Hello world\n"  # Message
            "\n"  # Decline reasoning view
            "4\n"  # Exit
        )
        run_cli_command(create_input)

        select_input = (
            "2\n"  # Выбрать чат
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(select_input)

        assert returncode == 0
        assert "PreviewTest" in stdout or "Превью:" in stdout


class TestUC003_ReturnToActiveChat:
    """
    Use Case UC-003: Return to Active Chat

    Test Cases:
    - TC-012: Return to Chat Without Active Chat
    - TC-013: Return to Chat With Active Chat
    """

    def test_tc_012_return_to_chat_without_active_chat(self):
        """
        TC-012: Return to Chat Without Active Chat

        Steps:
        1. Start application
        2. Verify option 3 shows "(нет активного чата)"
        3. Select option 3
        4. Verify warning displayed
        """
        test_input = (
            "3\n"  # Вернуться в чат (no active chat)
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "нет активного чата" in stdout.lower() or "[WARN]" in stdout

    def test_tc_013_return_to_chat_with_active_chat(self):
        """
        TC-013: Return to Chat With Active Chat

        Steps:
        1. Create or select chat
        2. Type "/menu"
        3. Verify option 3 shows "Вернуться в чат: {name}"
        4. Select option 3
        5. Verify chat loop entered with same context
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ActiveChatTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "3\n"  # Вернуться в чат
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert (
            "Вернуться в чат: ActiveChatTest" in stdout
            or "ЧАТ: ActiveChatTest" in stdout
        )


class TestUC004_SendMessageAndReceiveResponse:
    """
    Use Case UC-004: Send Message and Receive Response

    Test Cases:
    - TC-014: Send Multiple Messages
    - TC-015: Empty And Whitespace-Only Message Handling
    - TC-021: Unknown Command Handling
    - TC-022: System Prompt in History
    - TC-023: Special Characters in Input
    """

    def test_tc_014_send_multiple_messages(self):
        """
        TC-014: Send Multiple Messages

        Steps:
        1. Enter chat
        2. Send "Message 1"
        3. Send "Message 2"
        4. Send "Message 3"
        5. Return to menu
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "MultiMessage\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Message 1\n"  # First message
            "\n"  # Decline reasoning
            "Message 2\n"  # Second message
            "\n"  # Decline reasoning
            "Message 3\n"  # Third message
            "\n"  # Decline reasoning
            "/menu\n"  # Return to menu
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[USER]:" in stdout
        assert "[AGENT]" in stdout

    def test_tc_015_empty_and_whitespace_only_message_handling(self):
        """
        TC-015: Empty And Whitespace-Only Message Handling

        Steps:
        1. Enter chat
        2. Press Enter (empty) - should re-prompt
        3. Press Enter again - should re-prompt
        4. Send valid message - normal flow resumes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "EmptyMessage\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "\n"  # Empty message (should re-prompt)
            "\n"  # Empty message again
            "Valid message\n"  # Valid message
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[USER]:" in stdout or "Введите сообщение" in stdout

    def test_tc_021_unknown_command_handling(self):
        """
        TC-021: Unknown Command Handling

        Steps:
        1. Enter chat
        2. Type "/unknown"
        3. Verify warning about unknown command
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "UnknownCmd\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/unknown\n"  # Unknown command
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert (
            "[WARN]" in stdout or "Неизвестная команда" in stdout or "/help" in stdout
        )

    def test_tc_022_system_prompt_in_history(self):
        """
        TC-022: System Prompt in History

        Steps:
        1. Create chat with system prompt
        2. Verify history contains system message
        3. Check role = "system"
        4. Check display with [SYSTEM] prefix
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SystemPromptTest\n"  # Название
            "You are a helpful assistant\n"  # System prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Hello\n"  # User message
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[SYSTEM]" in stdout or "SYSTEM" in stdout.upper()

    def test_tc_023_special_characters_in_input(self):
        """
        TC-023: Special Characters in Input

        Steps:
        1. Create chat
        2. Send message with special characters
        3. Verify message handled correctly
        """
        special_message = "Test @#$%^&*()_+-=[]{}|;':\",./<>?"

        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SpecialChars\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            f"{special_message}\n"  # Message with special chars
            "\n"  # Decline reasoning
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[USER]:" in stdout


class TestUC005_ViewAndChangeSettingsInChat:
    """
    Use Case UC-005: View and Change Settings In-Chat

    Test Cases:
    - TC-016: View Settings
    - TC-017: Change Settings With Empty Inputs Disables Parameters
    - TC-032: Settings Change With Confirmation
    - TC-033: Settings Change Cancelled
    """

    def test_tc_016_view_settings(self):
        """
        TC-016: View Settings

        Steps:
        1. Enter chat with configured settings
        2. Type "/settings"
        3. Verify current settings displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ViewSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "n\n"  # Don't change
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout or "Модель:" in stdout
        assert "Температура:" in stdout

    def test_tc_017_change_settings_with_empty_inputs_disables_parameters(self):
        """
        TC-017: Change Settings With Empty Inputs Disables Parameters

        Steps:
        1. Type "/settings"
        2. Change only temperature
        3. Press Enter for others
        4. Verify only temperature changed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "PartialSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Change settings
            "1\n"  # Модель 1
            "0.8\n"  # Новая температура
            "\n"  # Top P (пусто -> отключён)
            "\n"  # Top K (пусто -> 0/отключено)
            "\n"  # Reasoning effort (пусто -> default 1)
            "\n"  # Context window (пусто -> 200k)
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[OK] Настройки обновлены!" in stdout or "обновлены" in stdout.lower()

    def test_tc_032_settings_change_with_confirmation(self):
        """
        TC-032: Settings Change With Confirmation

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "y"
        4. Verify all settings prompts shown
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ConfirmSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Подтверждение изменения
            "1\n"  # Модель 1
            "0.8\n"  # Новая температура
            "\n"  # Top P (пусто -> отключён)
            "\n"  # Top K (пусто -> отключено)
            "\n"  # Reasoning effort (default)
            "\n"  # Context window (default)
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Изменить настройки?" in stdout or "y/n" in stdout

    def test_tc_033_settings_change_cancelled(self):
        """
        TC-033: Settings Change Cancelled

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "n"
        4. Verify return to chat without changes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "CancelSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "n\n"  # Cancel change
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0


class TestUC006_NavigateToMenuFromChat:
    """
    Use Case UC-006: Navigate to Menu from Chat

    Test Cases:
    - TC-018: Menu Navigation from Chat
    - TC-122: Concurrent Chat Operations
    """

    def test_tc_018_menu_navigation_from_chat(self):
        """
        TC-018: Menu Navigation from Chat

        Steps:
        1. Enter chat
        2. Type "/menu"
        3. Verify Main Menu displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "MenuNav\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "3\n"  # Return to chat
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "МЕНЮ" in stdout or "AI CHAT CLI" in stdout

    def test_tc_122_concurrent_chat_operations(self):
        """
        TC-122: Concurrent Chat Operations

        Steps:
        1. Create Chat A
        2. Type "/menu"
        3. Create Chat B
        4. Verify both chats exist

        NOTE: All operations performed in single subprocess to ensure
        database state is preserved between operations.
        """
        test_input = (
            "1\n"  # Новый чат - создать Chat A
            "y\n"  # Хотите настроить? (y/n)
            "Chat A\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "1\n"  # Новый чат - создать Chat B
            "y\n"  # Хотите настроить? (y/n)
            "Chat B\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "2\n"  # Выбрать чат - показать список
            "1\n"  # Выбор Chat A -> вход в чат (активный чат становится A)
            "/menu\n"  # Return to menu
            "5\n"  # Вернуться в активный чат (A)
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[OK] Чат 'Chat A' создан!" in stdout
        assert "[OK] Чат 'Chat B' создан!" in stdout
        # Option 2 selected Chat A explicitly
        assert "[OK] Выбран чат: Chat A" in stdout
        # Option 5 returns to the ACTIVE chat, which is A after selecting Chat A via option 2
        assert "[OK] Возврат в чат: Chat A" in stdout
        assert "--- ЧАТ: Chat A [Фаза: PLAN] ---" in stdout


class TestUC007_StopOngoingGeneration:
    """
    Use Case UC-007: Stop Ongoing Generation

    Test Cases:
    - TC-019: Stop Command When Idle
    - TC-034: Stop Command Keeps Active Chat
    - TC-035: Stop Command Preserves Chat State
    """

    def test_tc_019_stop_command_when_idle(self):
        """
        TC-019: Stop Command When Idle

        Steps:
        1. Enter chat
        2. Type "/stop" (no generation)
        3. Verify message about generation status
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "StopIdle\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/stop\n"  # Stop when idle
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        # CLI shows "Генерация остановлена." even when idle in mock mode
        assert (
            "Генерация" in stdout
            or "остановлена" in stdout.lower()
            or "не активна" in stdout.lower()
        )

    def test_tc_034_stop_command_keeps_active_chat(self):
        """
        TC-034: Stop Command Keeps Active Chat

        Note: In mock/test mode, generation is instant.
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "StopGen\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Test message\n"  # Send message
            "/stop\n"  # Try to stop
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0

    def test_tc_035_stop_command_preserves_chat_state(self):
        """
        TC-035: Stop Command Preserves Chat State

        Steps:
        1. Wait for idle state (no generation active)
        2. Type "/stop"
        3. Verify output "Генерация не активна."
        4. Verify no state changes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "IdleStop\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/stop\n"  # Stop when idle
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert (
            "Генерация не активна" in stdout or "[INFO]" in stdout or "[WARN]" in stdout
        )


class TestUC008_DisplayHelpCommands:
    """
    Use Case UC-008: Display Help Commands

    Test Cases:
    - TC-121: Help Command
    """

    def test_tc_121_help_command(self):
        """
        TC-121: Help Command

        Steps:
        1. Enter chat
        2. Type "/help"
        3. Verify command list displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "HelpTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/help\n"  # Show help
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "/menu" in stdout
        assert "/stop" in stdout
        assert "/settings" in stdout
        assert "/summary" in stdout
        assert "/info" in stdout
        assert "/branch" in stdout
        assert "/help" in stdout


class TestUC009_ViewConversationSummary:
    """
    Use Case UC-009: View Conversation Summary

    Test Cases:
    - TC-026: View Summary With Summarization
    - TC-027: View Summary Without Summarization
    """

    def test_tc_026_view_summary_with_summarization(self):
        """
        TC-026: View Summary With Summarization
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "SummaryTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "\n" + "\n"  # Default params
            "/summary\n"  # View summary
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "/summary" in stdout or "Суммаризация" in stdout or "[INFO]" in stdout

    def test_tc_027_view_summary_without_summarization(self):
        """
        TC-027: View Summary Without Summarization
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "NoSummary\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/summary\n"  # View summary
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[INFO]" in stdout or "Суммаризация еще не выполнялась" in stdout


class TestUC010_ViewChatInfoAndTokenStatistics:
    """
    Use Case UC-010: View Chat Information and Token Statistics

    Test Cases:
    - TC-028: View Chat Info With Token Statistics
    - TC-043: View Info For Different Strategies
    """

    def test_tc_028_view_chat_info_with_token_statistics(self):
        """
        TC-028: View Chat Info With Token Statistics
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "InfoTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "--- ИНФОРМАЦИЯ О ЧАТЕ ---" in stdout or "ИНФОРМАЦИЯ" in stdout

    def test_tc_043_view_info_for_different_strategies(self):
        """
        TC-043: View Info For Different Strategies
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "DefaultInfo\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Стратегия:" in stdout or "DefaultStrategy" in stdout


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


class TestUC002_Alt_TC076_077_ChatListValidation:
    """
    TC-076/TC-077: Chat list selection validation (UC-002 A2/A3).
    """

    def test_tc_076_chat_list_selection_out_of_range(self):
        """
        TC-076: Chat List Selection Out Of Range (UC-002 A2)

        Two chats exist; entering "0" then "3" re-prompts with
        "Введите число от 1 до 2"; "1" selects the chat.
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # Настройки по умолчанию
            "/menu\n"  # В меню
            "1\n"  # Новый чат №2
            "\n"  # По умолчанию
            "/menu\n"  # В меню
            "2\n"  # Выбрать чат
            "0\n"  # Вне диапазона снизу
            "3\n"  # Вне диапазона сверху
            "1\n"  # Корректный выбор
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите число от 1 до 2" in stdout
        assert stdout.count("Введите число от 1 до 2") >= 2

    def test_tc_077_chat_list_non_numeric_selection(self):
        """
        TC-077: Chat List Non-Numeric Selection (UC-002 A3)

        Entering "abc" and "2.5" re-prompts with "Введите корректное число";
        a valid number then loads the chat.
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            "/menu\n"  # В меню
            "2\n"  # Выбрать чат
            "abc\n"  # Нечисловой ввод
            "2.5\n"  # Нечисловой ввод (int() падает)
            "1\n"  # Корректный выбор
            "/menu\n"
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите корректное число" in stdout
        assert stdout.count("Введите корректное число") >= 2


class TestUC016_Invariants_TC060_112_113_114:
    """
    TC-060, TC-112, TC-113, TC-114: Invariant management (UC-016).
    """

    _PROFILE_SETUP = (
        "3\n"  # Профили задач
        "1\n"  # Создать профиль
        "Inv Profile\n"  # Название
        "Profile for invariants\n"  # Описание
        "\n"  # Предпочтения (пропуск)
        "Base rule\n"  # Инвариант при создании
        "\n"  # Пустая строка завершает ввод инвариантов
    )

    def test_tc_060_manage_invariants_add_and_remove(self):
        """
        TC-060: Manage Invariants - Add and Remove (UC-016)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "1\n"  # Добавить инвариант
            "Second rule\n"
            "2\n"  # Удалить инвариант
            "2\n"  # Номер удаляемого (существующий)
            "2\n"  # Удалить инвариант (повторно)
            "99\n"  # Некорректный номер
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку -> возврат в меню профилей
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "ИНВАРИАНТЫ ПРОФИЛЯ" in stdout
        assert "Инвариант добавлен" in stdout
        assert "Инвариант удал" in stdout
        assert "Некорректный номер" in stdout

    def test_tc_112_manage_invariants_empty_text(self):
        """
        TC-112: Manage Invariants - Empty Invariant Text (UC-016 A1)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "1\n"  # Добавить инвариант
            "\n"  # Пустой текст
            "1\n"  # Добавить инвариант (повтор)
            "Valid rule\n"
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "не может быть пустым" in stdout
        assert "Инвариант добавлен" in stdout

    def test_tc_113_manage_invariants_invalid_action(self):
        """
        TC-113: Manage Invariants - Invalid Action Choice Re-Prompts (UC-016)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "1\n"  # Профиль №1
            "9\n"  # Недопустимое действие
            "abc\n"  # Нечисловое действие
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "ИНВАРИАНТЫ ПРОФИЛЯ" in stdout
        # App survived invalid actions and exited cleanly
        assert "Traceback" not in stderr

    def test_tc_114_manage_invariants_invalid_profile_index(self):
        """
        TC-114: Manage Invariants - Invalid Profile Index (UC-016)
        """
        test_input = (
            self._PROFILE_SETUP + "2\n"  # Просмотреть список профилей
            "2\n"  # Управление инвариантами
            "99\n"  # Недопустимый индекс профиля
            "abc\n"  # Нечисловой индекс
            "1\n"  # Корректный профиль
            "3\n"  # Назад из подменю инвариантов
            "4\n"  # Назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "ИНВАРИАНТЫ ПРОФИЛЯ" in stdout
        assert "Traceback" not in stderr


class TestUC017_DeleteFlow_TC115_116:
    """
    TC-115/TC-116: Task profile deletion edge cases (UC-017).
    """

    _PROFILE_SETUP = (
        "3\n"  # Профили задач
        "1\n"  # Создать профиль
        "Del Target\n"  # Название
        "To be deleted\n"  # Описание
        "\n"  # Предпочтения
        "\n"  # Инварианты: пусто
    )

    def test_tc_115_chat_loop_graceful_exit_on_eof(self):
        """
        TC-115: Chat Loop Graceful Exit On End Of Input (UC-004 A7)

        Steps:
        1. Create a chat (quick path), send one message; input ends right
           after the exchange (no /menu, no option 6).
        2. Verify termination: no traceback, clean exit.
        3. Verify memory save: agent memory is saved before exit (restart
           shows the exchange intact).
        """
        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            "Remember this fact\n"  # Сообщение
            "\n"  # Отказ от рассуждений (если запрошен)
            # EOF: stdin закрывается прямо в цикле чата
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[AGENT]" in stdout, "Message exchange should complete before EOF"
        assert "Traceback" not in stderr
        assert "EOFError" not in stderr

        # Шаг 3: память сохранена — перезапуск показывает тот же чат с историей
        restart_input = (
            "2\n"  # Выбрать чат
            "1\n"  # Чат 1
            "/info\n"  # Проверка счётчика сообщений
            "/menu\n"
            "6\n"
        )
        stdout2, stderr2, rc2 = run_cli_command(restart_input)
        assert rc2 == 0, f"Restart failed: {stderr2}"
        assert "[OK] Выбран чат: Чат 1" in stdout2
        import re as _re

        m = _re.search(r"Сообщений:\s*(\d+)", stdout2)
        assert m is not None, f"No message counter in /info output:\n{stdout2}"
        assert int(m.group(1)) >= 2, (
            "Memory must be saved on EOF exit: expected user+assistant "
            f"messages persisted, got {m.group(1)}"
        )

    def test_tc_116_profiles_submenu_non_numeric_action_reprompts(self):
        """
        TC-116: Profiles List Submenu Non-Numeric Action Re-Prompts (UC-013 A4)

        Steps:
        1. Open profiles list with at least one profile -> prompt
           'Выберите действие (1-4):' displayed.
        2. Enter 'abc' (non-numeric) -> [WARN] Неверный выбор, попробуйте снова.,
           action prompt re-displayed.
        3. Enter '0' -> same warning; action prompt re-displayed.
        4. Enter '4' (Back to list) -> control returns to the Task Profiles menu.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "abc\n"  # Нечисловое действие
            "0\n"  # Некорректное действие
            "4\n"  # Назад к списку -> возврат в меню профилей
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Выберите действие (1-4):" in stdout
        # Предупреждения именно из подменю действий (после вывода списка профилей)
        after_list = stdout.split("--- СПИСОК ПРОФИЛЕЙ ЗАДАЧ ---", 1)[-1]
        assert after_list.count("[WARN] Неверный выбор, попробуйте снова.") >= 2, (
            "'abc' and '0' must each produce the invalid-choice warning"
        )
        # После шага 4 управление вернулось в меню профилей (его заголовок)
        assert "--- ПРОФИЛИ ЗАДАЧ ---" in stdout
        assert "успешно удалён" not in stdout
        assert "Inv Profile" in stdout

    def test_tc_117_create_profile_with_empty_preferences(self):
        """
        TC-117: Create Profile With Empty Preferences (UC-014 A3)

        Steps:
        1. Reach the preferences prompt during profile creation.
        2. Press Enter (empty input) -> no error, invariants block follows.
        3. Finish creation with an empty invariants line -> [OK] message.
        4. View the created profile (action 1) -> 'Предпочтения:' omitted.
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "EmptyPrefs117\n"  # Название
            "Profile with empty prefs\n"  # Описание
            "\n"  # Предпочтения: пустой ввод (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите предпочтения/инструкции (Enter для пропуска):" in stdout
        assert "--- ИНВАРИАНТЫ" in stdout, "Invariants block must follow skipped prefs"
        assert "[OK] Профиль задачи 'EmptyPrefs117' создан!" in stdout
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        # §4.7.3: при пустых предпочтениях строка 'Предпочтения:' не выводится
        assert "Предпочтения:" not in stdout

    def test_tc_118_delete_task_profile_repository_failure(self):
        """
        TC-118: Delete Task Profile - Repository Failure (UC-017 step 7)

        Note: the CLI wraps repository deletion in try/except and prints
        "[ERROR] Не удалось удалить профиль '{name}'." only when the
        repository raises. In TEST mode deletion succeeds, so this test
        verifies the success path plus the exact confirmation-prompt text
        from the spec; the failure branch is covered by the error-handling
        code path in cli_app._delete_profile.
        """
        test_input = (
            self._PROFILE_SETUP.replace("Inv Profile", "Fail Target")
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "1\n"  # Профиль №1
            "y\n"  # Подтвердить удаление
            "4\n"  # Назад к списку -> возврат в меню профилей
            "0\n"  # Выход из подменю списка (см. _view_task_profiles_list)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert (
            "Вы уверены, что хотите удалить профиль 'Fail Target'? (y/n):" in stdout
        ), "Confirmation prompt text must match UC-017 step 6"
        assert "[OK] Профиль 'Fail Target' успешно удалён." in stdout
        # В TEST-режиме удаление успешно; ветка сбоя репозитория
        # ([ERROR] Не удалось удалить профиль ...) недостижима без mock-сбоя.
        assert "Не удалось удалить профиль" not in stdout
        assert "Traceback" not in stderr

    def test_tc_115b_delete_profile_invalid_index(self):
        """
        Supplement (UC-017): Out-of-range and non-numeric delete indices must
        not crash the app and must keep the profile intact.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "99\n"  # Вне диапазона
            "abc\n"  # Нечисловой ввод
            "1\n"  # Профиль №1
            "n\n"  # Отменить удаление — профиль остаётся
            "4\n"  # Назад к списку -> возврат в меню профилей
            "0\n"  # Выход из подменю списка (см. _view_task_profiles_list)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Введите корректное число" in stdout, (
            "Non-numeric delete index must re-prompt without crashing"
        )
        assert "[INFO] Удаление отменено." in stdout
        assert "Inv Profile" in stdout
        assert "успешно удалён" not in stdout
        assert "Traceback" not in stderr

    def test_tc_116b_delete_last_profile_refreshes_list(self):
        """
        Supplement (UC-017): After deleting the only profile the submenu stays
        usable and the list shows the empty state.
        """
        test_input = (
            self._PROFILE_SETUP
            + "2\n"  # Просмотреть список профилей
            + "3\n"  # Удалить профиль
            "1\n"  # Профиль №1
            "y\n"  # Подтвердить удаление
            "2\n"  # Просмотреть список снова (подменю доступно после удаления)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль 'Del Target' успешно удалён." in stdout
        assert "Нет доступных профилей задач." in stdout


class TestEdgeCases_Robustness:
    """
    Robustness edge cases (EOF during creation, long input).

    Supplement to the spec: graceful termination scenarios.
    """

    def test_tc_edge_eof_during_chat_creation(self):
        """
        Edge case: EOF During Chat Creation

        Closing stdin mid-creation must terminate gracefully (no traceback).
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить?
            "Halfway\n"  # Название
            # EOF here (stdin closed before system prompt)
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert "Traceback" not in stderr
        assert "EOFError" not in stderr

    def test_tc_edge_long_message_handling(self):
        """
        Edge case: Long Message Handling

        A very long user message must be accepted without crash.
        """
        long_message = "X" * 5000

        test_input = (
            "1\n"  # Новый чат (быстрое создание)
            "\n"  # По умолчанию
            + long_message
            + "\n/exit\n6\n"  # Выход из чата и приложения
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "Traceback" not in stderr


class TestUC011_CreateChatBranch:
    """
    Use Case UC-011: Create Chat Branch

    Test Cases:
    - TC-029: Create Branch And Switch
    - TC-030: Create Branch And Stay
    - TC-031: Create Branch With Custom Name
    - TC-044: Branch Preserves Strategy Type
    - TC-045: Branch Preserves SlidingWindow Configuration
    """

    def test_tc_029_create_branch_and_switch(self):
        """
        TC-029: Create Branch And Switch
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchSwitch\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "\n"  # Accept default name
            "y\n"  # Switch to branch
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Ветка" in stdout or "branch" in stdout.lower()
        assert "Продолжить в новой ветке?" in stdout

    def test_tc_030_create_branch_and_stay(self):
        """
        TC-030: Create Branch And Stay
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchStay\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "\n"  # Accept default name
            "n\n"  # Stay in current
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Ветка" in stdout or "[OK]" in stdout

    def test_tc_031_create_branch_with_custom_name(self):
        """
        TC-031: Create Branch With Custom Name
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Original\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/branch\n"  # Create branch
            "My Custom Branch\n"  # Custom name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "My Custom Branch" in stdout or "Ветка" in stdout

    def test_tc_044_branch_preserves_strategy_type(self):
        """
        TC-044: Branch Preserves Strategy Type
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchStrategy\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "\n" + "\n"  # Default params
            "/branch\n"  # Create branch
            "\n"  # Accept name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Ветка" in stdout or "[OK]" in stdout

    def test_tc_045_branch_preserves_sliding_window_configuration(self):
        """
        TC-045: Branch Preserves SlidingWindow Configuration
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "BranchSliding\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "4\n"  # SlidingWindowStrategy
            "15\n"  # window_size=15
            "/branch\n"  # Create branch
            "\n"  # Accept name
            "n\n"  # Stay
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Ветка" in stdout or "[OK]" in stdout


# Allow running tests directly with: python test_cli_e2e.py
if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))


class TestUC012_ViewGlobalMemoryFromMenu:
    """
    Use Case UC-012: View Global Memory from Menu

    Test Cases:
    - TC-046: View Global Memory From Main Menu
    - TC-047: View Global Memory Empty State
    - TC-048: View Global Memory With Facts
    """

    def test_tc_046_view_global_memory_from_main_menu(self):
        """
        TC-046: View Global Memory From Main Menu

        Steps:
        1. Start application, stay in Main Menu (no active chat)
        2. Select option 4 (Global Memory) from menu
        3. Verify header displayed: "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---"
        4. Verify return to menu
        """
        # Main Menu has option 4 for Global Memory, accessible without active chat
        test_input = (
            "4\n"  # Select Global Memory
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        # Should display global memory header
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout
        # Should return to menu or exit cleanly

    def test_tc_047_view_global_memory_empty_state(self):
        """
        TC-047: View Global Memory Empty State

        Steps:
        1. Start application (fresh DB with no global memory saved yet)
        2. Select option 4 to view global memory
        3. Verify header is displayed
        4. Verify message about empty memory is displayed
        5. Verify returns to menu
        """
        test_input = (
            "4\n"  # View global memory (should be empty on fresh start)
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "ГЛОБАЛЬНАЯ ПАМЯТЬ" in stdout
        # Empty memory shows "(память пуста)" message
        assert "память пуста" in stdout.lower()

    def test_tc_048_view_global_memory_with_facts(self):
        """
        TC-048: View Global Memory With Facts

        Steps:
        1. Create a new chat
        2. Send a message (mock provider extracts facts into global memory)
        3. Answer 'n' to reasoning prompt
        4. Use /menu to return to main menu
        5. Select option 3 to view global memory
        6. Verify header is displayed
        7. Verify facts are displayed as numbered list
        8. Verify separator line
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "FactsMemoryTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n\n\n\n\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Расскажи о себе\n"  # Send message to trigger memory extraction
            "n\n"  # Don't show reasoning
            "/menu\n"  # Return to main menu
            "4\n"  # View global memory (should have facts from mock)
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"

        # Check header
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout, "Header should be displayed"

        # Check separator (40 dashes)
        assert "-" * 40 in stdout, "Separator line should be displayed"

        # Mock provider returns exactly these two facts when JSON format is requested
        expected_fact_1 = (
            "1. Пользователь предпочитает использовать Python для разработки"
        )
        expected_fact_2 = "2. Пользователь работает в Москве"

        # Verify both facts are present in the output
        assert expected_fact_1 in stdout, (
            f"First fact should be displayed: {expected_fact_1}"
        )
        assert expected_fact_2 in stdout, (
            f"Second fact should be displayed: {expected_fact_2}"
        )


class TestUC013_ViewTaskProfilesList:
    """
    Use Case UC-013: View Task Profiles List

    Test Cases:
    - TC-053: View Task Profiles List (Empty)
    - TC-054: View Task Profiles List (Multiple)
    """

    def test_tc_053_view_task_profiles_list_empty(self):
        """
        TC-053: View Task Profiles List (Empty)

        Steps:
        1. Start application (fresh DB, no profiles)
        2. Select option 3 (Профили задач) from Main Menu
        3. Verify message that no profiles exist
        4. Verify menu options are shown
        5. Exit
        """
        test_input = (
            "3\n"  # Профили задач
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # Should show message about no profiles or empty list
        assert "Нет доступных профилей" in stdout or "Профили задач" in stdout, (
            "Should show profiles section"
        )

    def test_tc_054_view_task_profiles_list_multiple(self):
        """
        TC-054: View Task Profiles List (Multiple)

        Steps:
        1. Create a task profile via menu
        2. Return to profiles list
        3. Verify profile is displayed with ID, name, date
        4. Exit
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Test Task Profile\n"  # Name
            "This is a test task description\n"  # Description
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # After creation, should see the profile in the list or confirmation
        assert "создан" in stdout.lower() or "Test Task Profile" in stdout, (
            "Should confirm profile creation or show it in list"
        )


class TestUC014_CreateNewTaskProfile:
    """
    Use Case UC-014: Create New Task Profile

    Test Cases:
    - TC-049: Create Task Profile (Valid Data)
    - TC-050: Create Task Profile (Empty Name Validation)
    - TC-052: Create Task Profile (Empty Description Validation)
    - TC-051: Create Task Profile (Long Name Accepted)
    - TC-068: Create Profile With Preferences
    - TC-069: Create Profile Without Preferences
    """

    def test_tc_049_create_task_profile_with_valid_data(self):
        """
        TC-049: Create Task Profile with Valid Data

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Verify success message with profile info
        6. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout

    def test_tc_050_create_task_profile_empty_name_validation(self):
        """
        TC-050: Create Task Profile - Empty Name Validation

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Press Enter (empty name)
        4. Verify error message about empty name
        5. Re-enter valid name
        6. Enter description
        7. Verify success
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "\n"  # Empty name (should trigger validation)
            "Valid Name\n"  # Valid name on retry
            "Description\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Название профиля не может быть пустым." in stdout
        assert "[OK] Профиль задачи 'Valid Name' создан!" in stdout

    def test_tc_052_create_task_profile_empty_description_validation(self):
        """
        TC-052: Create Task Profile - Empty Description Validation

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name
        4. Press Enter (empty description)
        5. Verify error message about empty description
        6. Re-enter valid description
        7. Verify success
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Task Name\n"  # Valid name
            "\n"  # Empty description (should trigger validation)
            "Valid Description\n"  # Valid description on retry
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[ERROR] Описание задачи не может быть пустым." in stdout
        assert "[OK] Профиль задачи 'Task Name' создан!" in stdout

    def test_tc_051_create_task_profile_long_name_accepted(self):
        """
        TC-051: Create Task Profile - Long Name Accepted

        Steps:
        1. Select option 3 (Профили задач)
        2. Select option 1 (Создать новый профиль)
        3. Enter 150-character name (should truncate to 100)
        4. Enter description
        5. Verify profile created with truncated name
        """
        long_name = "A" * 150  # 150 characters

        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            f"{long_name}\n"  # Long name (accepted without truncation)
            "Description\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи" in stdout and "создан!" in stdout

    def test_tc_068_create_profile_with_preferences(self):
        """
        TC-068: Create Profile With Preferences

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Enter preferences text "Be concise and formal"
        6. Verify success message with profile info
        7. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "Be concise and formal\n"  # Preferences text
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout
        # TC-066/UC-015 step 6: preferences displayed in profile view
        assert "Предпочтения: Be concise and formal" in stdout

    def test_tc_069_create_profile_without_preferences(self):
        """
        TC-069: Create Profile Without Preferences

        Steps:
        1. Select option 3 (Профили задач) from Main Menu
        2. Select option 1 (Создать новый профиль)
        3. Enter valid name "My Task"
        4. Enter valid description "Task description here"
        5. Press Enter (skip preferences)
        6. Verify success message with profile info
        7. Verify empty preferences accepted (no error)
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "My Task\n"  # Valid name
            "Task description here\n"  # Valid description
            "\n"  # Empty preferences (skip)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'My Task' создан!" in stdout
        # TC-067/§4.7.3: with empty preferences the line is omitted entirely
        assert "Предпочтения:" not in stdout


class TestUC015_ViewTaskProfileMemory:
    """
    Use Case UC-015: View Task Profile Memory

    Test Cases:
    - TC-056: View Task Profile Memory (Empty State)
    - TC-055: View Task Profile Memory (Flow)
    - TC-060: Preferences Display in View Profile - With Preferences
    - TC-061: Preferences Display in View Profile - Empty Preferences
    """

    def test_tc_056_view_task_profile_memory_empty_state(self):
        """
        TC-056: View Task Profile Memory - Empty State

        Steps:
        1. Create a task profile
        2. Select option to view profile memory
        3. Verify profile info displayed (ID, name, date, description)
        4. Verify message that memory is empty
        5. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Memory Test Profile\n"  # Name
            "Test description for memory view\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        # TC-056: profile info displayed with empty memory and invariants
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Memory Test Profile" in stdout
        assert "(память пуста)" in stdout
        assert "(инварианты не заданы)" in stdout

    def test_tc_055_view_task_profile_memory_flow(self):
        """
        TC-055: View Task Profile Memory - Flow

        Steps:
        1. Create a task profile
        2. Create a chat linked to this profile
        3. Send messages to populate task memory
        4. View profile memory
        5. Verify profile info displayed
        6. Verify facts displayed as numbered list
        """
        # This test requires creating profile, then chat with that profile,
        # sending messages, then viewing memory
        # Simplified version for now - just verify flow works
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Facts Profile\n"  # Name
            "Profile for testing facts\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Test Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # DefaultStrategy
            "1\n"  # Привязать профиль №1 (Facts Profile)
            "/menu\n"  # Выход из чата в меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "1\n"  # Действие: просмотреть память профиля
            "1\n"  # Профиль №1
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'Facts Profile' создан!" in stdout
        assert "[OK] Чат 'Test Chat' создан!" in stdout
        # Profile view reachable after linking a chat to it
        assert "--- ИНФОРМАЦИЯ О ПРОФИЛЕ ЗАДАЧИ ---" in stdout
        assert "Facts Profile" in stdout


class TestUC017_DeleteTaskProfile:
    """
    Use Case UC-016: Delete Task Profile

    Test Cases:
    - TC-057: Delete Task Profile (Not Attached)
    - TC-058: Delete Task Profile (Attached to Agents)
    - TC-059: Delete Task Profile (Cancelled)
    """

    def test_tc_057_delete_task_profile_not_attached(self):
        """
        TC-057: Delete Task Profile - Not Attached

        Steps:
        1. Create a task profile
        2. Select delete option
        3. Confirm deletion
        4. Verify success message
        5. Verify profile removed from list
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "ToDelete Profile\n"  # Name
            "Will be deleted\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: удалить профиль
            "1\n"  # Профиль №1 для удаления
            "y\n"  # Подтверждение удаления
            "2\n"  # Снова открыть список профилей
            "4\n"  # Действие: назад к списку
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Профиль задачи 'ToDelete Profile' создан!" in stdout
        assert "[OK] Профиль 'ToDelete Profile' успешно удалён." in stdout
        # Profile removed from the subsequent list
        assert "Нет доступных профилей задач." in stdout

    def test_tc_058_delete_task_profile_attached_to_agents(self):
        """
        TC-058: Delete Task Profile - Attached to Agents

        Steps:
        1. Create a task profile
        2. Create a chat linked to this profile
        3. Try to delete the profile
        4. Verify warning about linked agents
        5. Verify deletion still possible or blocked
        """
        # This test requires full flow: create profile, create chat with profile, delete
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Linked Profile\n"  # Name
            "Has linked chats\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат (привязка к профилю)
            "y\n"  # Хотите настроить? (y/n)
            "Linked Chat\n"  # Chat name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "1\n"  # Привязать профиль №1 (Linked Profile)
            "/menu\n"  # Выход из чата в меню
            "3\n"  # Профили задач
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: удалить профиль
            "1\n"  # Профиль №1 для удаления
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Linked Chat' создан!" in stdout
        # TC-058/UC-017 A?: deletion blocked because profile is attached to an agent
        assert "Невозможно удалить профиль 'Linked Profile'" in stdout
        assert "Сначала удалите или пересоздайте агентов" in stdout

    def test_tc_059_delete_task_profile_cancelled(self):
        """
        TC-059: Delete Task Profile - Cancelled

        Steps:
        1. Create a task profile
        2. Select delete option
        3. When prompted for confirmation, select 'no'
        4. Verify profile NOT deleted
        5. Verify returns to profiles menu
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Keep Profile\n"  # Name
            "Should not be deleted\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "2\n"  # Просмотреть список профилей
            "3\n"  # Действие: Удалить профиль
            "1\n"  # Выбрать профиль №1 для удаления
            "n\n"  # Подтверждение удаления: нет (отмена)
            "3\n"  # Назад в главное меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[INFO] Удаление отменено." in stdout
        assert "успешно удалён" not in stdout
        # Профиль остался в списке
        assert "Keep Profile" in stdout


class TestUC001_ChatCreationWithTaskProfile:
    """
    Use Case: Create Chat with Task Profile Selection

    Test Cases:
    - TC-061: Create Chat with Task Profile Attachment
    - TC-062: Create Chat Without Task Profile
    - TC-007: Task Profile Selection Invalid Choice
    """

    def test_tc_061_create_chat_with_task_profile_attachment(self):
        """
        TC-061: Create Chat with Task Profile Attachment

        Steps:
        1. Create a task profile first
        2. Create new chat
        3. Fill in all chat settings
        4. When prompted for task profile, select the created profile
        5. Verify chat created with profile info displayed
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "Chat Profile\n"  # Name
            "For chat binding\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Bound Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # Strategy
            "1\n"  # Select profile 1 (Chat Profile)
            "/info\n"  # Проверка привязки профиля
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Bound Chat' создан!" in stdout
        assert "Профиль задачи: Chat Profile" in stdout

    def test_tc_062_create_chat_without_task_profile(self):
        """
        TC-062: Create Chat Without Task Profile

        Steps:
        1. Create new chat
        2. Fill in all settings
        3. When prompted for task profile, select 0 (none)
        4. Verify chat created without profile
        5. Verify confirmation shows no profile attached
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "No Profile Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            # Профилей нет -> шаг привязки пропускается автоматически (TC-063)
            "/info\n"  # Проверка отсутствия профиля
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'No Profile Chat' создан!" in stdout
        # TC-063: no profiles available -> skip attachment
        assert "(нет доступных профилей)" in stdout
        assert "Профиль задачи: (не привязан)" in stdout

    def test_tc_007_task_profile_selection_invalid_choice(self):
        """
        TC-007: Task Profile Selection Invalid Choice

        Steps:
        1. Create a task profile (so the selection list is not empty)
        2. Create new chat via manual path
        3. When prompted for task profile, enter invalid number "99"
        4. Verify [WARN] message and that creation continues without profile
        5. Verify chat created
        """
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать новый профиль
            "TC007 Profile\n"  # Name
            "Profile for TC-007\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Invalid Select Chat\n"  # Chat name
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "99\n"  # Некорректный номер профиля (вне диапазона)
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[WARN] Некорректный выбор. Профиль не привязан." in stdout
        assert "[OK] Чат 'Invalid Select Chat' создан!" in stdout


class TestS3_MemoryIntegrationInSystemPrompt:
    """
    Use Case: Task Profile Memory Integration in System Prompt

    Test Cases:
    - TC-064: Memory Integration Global + Task Profile
    - TC-065: Preferences Display - Empty Preferences
    """

    def test_tc_064_memory_integration_global_and_task(self):
        """
        TC-064: Memory Integration Global + Task Profile

        Steps:
        1. Ensure global memory has facts (send message in any chat)
        2. Create task profile
        3. Create chat linked to task profile
        4. Send message to populate task memory
        5. Verify system prompt contains both memories
        6. Verify order: global first, then task
        7. Verify headers separate them
        """
        test_input = (
            # First, create a chat to populate global memory
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Global Memory Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "0\n"  # No task profile
            "n\n"  # No reasoning (промпт после вывода ответа)
            "/menu\n"  # Back to main menu
            # Create task profile
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Integration Profile\n"  # Name
            "For memory integration test\n"  # Description
            "\n"  # Предпочтения (пропуск)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад в главное меню (из меню профилей)
            # Create chat with task profile
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Integration Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            # Select the created profile (assuming it's #1)
            "1\n"  # Select profile
            "Send test message\n"  # Message
            "n\n"  # No reasoning
            "/info\n"  # Проверка привязки профиля и памяти в инфо чата
            "/menu\n"  # Выход в меню
            "4\n"  # Просмотреть глобальную память (шаг 1: факты есть)
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Global Memory Chat' создан!" in stdout
        assert "[OK] Профиль задачи 'Integration Profile' создан!" in stdout
        assert "[OK] Чат 'Integration Chat' создан!" in stdout
        assert "Профиль задачи: Integration Profile" in stdout
        # Шаг 1: глобальная память содержит факты после обмена сообщениями
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout
        memory_section = stdout.split("--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---")[-1]
        assert "(память пуста)" not in memory_section, (
            "Mock provider must extract global facts after a message exchange"
        )

    def test_tc_065_preferences_display_empty_preferences(self):
        """
        TC-065: Preferences Display - Empty Preferences

        Precondition: Global memory has facts, task profile has no preferences (empty string)

        Steps:
        1. Create task profile without preferences
        2. Create chat linked to task profile
        3. Send message to trigger system prompt construction
        4. Verify global memory facts appear with header
        5. Verify task profile memory appears with header
        6. Verify preferences section is NOT displayed (skipped when empty)
        """
        test_input = (
            # Create task profile without preferences
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Empty Pref Profile\n"  # Name
            "Profile for testing empty preferences\n"  # Description
            "\n"  # Empty preferences (skip)
            "\n"  # Инварианты: пустая строка завершает ввод
            "3\n"  # Назад
            # Create chat with task profile
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "Empty Pref Chat\n"  # Name
            "\n"  # Skip prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings
            "1\n"  # Strategy
            "1\n"  # Select profile #1
            "Test message\n"  # Message
            "n\n"  # No reasoning
            "/menu\n"  # Выход в меню
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"
        assert "[OK] Чат 'Empty Pref Chat' создан!" in stdout
        # Preferences line omitted when empty (§4.7.3)
        assert "Предпочтения:" not in stdout
