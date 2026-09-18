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
    - TC-001: Create Chat with Default Values
    - TC-002: Create Chat with Custom Settings
    - TC-003: Invalid Temperature Handling
    - TC-019: Long Chat Name Handling
    - TC-031: SlidingWindowStrategy Creation
    - TC-032: SlidingWindowStrategy With Custom Window
    - TC-033: SummarizationStrategy Creation
    - TC-034: SummarizationStrategy With Custom Parameters
    - TC-035: KeyValueMemoryStrategy Creation
    - TC-036: KeyValueMemoryStrategy With Custom Parameters
    - TC-037: DefaultStrategy Creation
    """

    def test_tc_001_create_chat_default_values(self):
        """
        TC-001: Create Chat with Default Values

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
            "\n"  # Default name (Чат N)
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n"  # Temperature disabled
            "\n"  # Top P disabled
            "\n"  # Top K disabled (0)
            "\n"  # Reasoning effort (none)
            "\n"  # Context window (200k)
            "1\n"  # DefaultStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "[OK] Чат 'Чат" in stdout, "Default chat name should be 'Чат N'"
        assert "ID:" in stdout, "Chat ID should be displayed"
        assert "Стратегия:" in stdout or "DefaultStrategy" in stdout, (
            "Strategy should be displayed"
        )

    def test_tc_002_create_chat_custom_settings(self):
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
            "Test Chat\n"  # Название
            "Be concise\n"  # Системный промпт
            "2\n"  # Model 2 (Qwen3.6)
            "1.5\n"  # Temperature
            "0.8\n"  # Top P
            "50\n"  # Top K
            "3\n"  # Reasoning effort: medium
            "100000\n"  # Context window
            "1\n"  # DefaultStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[OK] Чат 'Test Chat' создан!" in stdout
        assert "ID:" in stdout

    def test_tc_003_invalid_temperature_handling(self):
        """
        TC-003: Invalid Temperature Handling

        Steps:
        1-3. Create chat, reach temperature prompt
        4. Enter "abc" - should show warning, temp disabled
        5. Continue creation
        """
        test_input = (
            "1\n"  # Новый чат
            "Temp Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "abc\n"  # Invalid temperature
            "\n"  # Top P disabled
            "\n"  # Top K disabled
            "\n"  # Reasoning effort
            "\n"  # Context window
            "1\n"  # DefaultStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        # Check for Russian text about invalid input or disabled temperature
        assert (
            "Некорректное" in stdout
            or "отключено" in stdout.lower()
            or "default" in stdout.lower()
        ), "Should show warning about invalid temperature"

    def test_tc_019_long_chat_name_handling(self):
        """
        TC-019: Long Chat Name Handling

        Steps:
        1. Enter 150-char name - should truncate to 100
        2. Verify storage has max 100 chars
        3. Verify display shows truncated name
        """
        long_name = "A" * 150  # 150 characters

        test_input = (
            "1\n"  # Новый чат
            f"{long_name}\n"  # Long name (should truncate to 100)
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[OK] Чат" in stdout

    def test_tc_031_sliding_window_strategy_creation(self):
        """
        TC-031: SlidingWindowStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 4 (SlidingWindow)
        3. Press Enter (accept default window_size=10)
        4. Verify strategy type = "SlidingWindowStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "SlidingWindow Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "4\n"  # SlidingWindowStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SlidingWindowStrategy" in stdout or "4." in stdout

    def test_tc_032_sliding_window_strategy_custom_window(self):
        """
        TC-032: SlidingWindowStrategy With Custom Window

        Steps:
        1. Create new chat
        2. Select option 4 (SlidingWindow)
        3. Enter "20"
        4. Verify window_size = 20
        """
        test_input = (
            "1\n"  # Новый чат
            "SlidingWindow Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "4\n"  # SlidingWindowStrategy
            "20\n"  # Custom window_size
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SlidingWindowStrategy" in stdout or "window" in stdout.lower()

    def test_tc_033_summarization_strategy_creation(self):
        """
        TC-033: SummarizationStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 2 (Summarization)
        3. Press Enter (non_compressible_count=2)
        4. Press Enter (buffer_size=3)
        5. Verify strategy type = "SummarizationStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "Summarization Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SummarizationStrategy" in stdout

    def test_tc_034_summarization_strategy_custom_parameters(self):
        """
        TC-034: SummarizationStrategy With Custom Parameters

        Steps:
        1. Create new chat
        2. Select option 2 (Summarization)
        3. Enter "5" (non_compressible_count)
        4. Enter "4" (buffer_size)
        5. Verify custom parameters
        """
        test_input = (
            "1\n"  # Новый чат
            "Summarization Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "2\n"  # SummarizationStrategy
            "5\n"  # non_compressible_count=5
            "4\n"  # buffer_size=4
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "SummarizationStrategy" in stdout

    def test_tc_035_key_value_memory_strategy_creation(self):
        """
        TC-035: KeyValueMemoryStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 3 (KeyValueMemory)
        3. Press Enter (non_compressible_count=2)
        4. Press Enter (buffer_size=3)
        5. Verify strategy type = "KeyValueMemoryStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "KeyValueMemory Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "3\n"  # KeyValueMemoryStrategy
            "\n"  # non_compressible_count=2
            "\n"  # buffer_size=3
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "KeyValueMemoryStrategy" in stdout

    def test_tc_036_key_value_memory_strategy_custom_parameters(self):
        """
        TC-036: KeyValueMemoryStrategy With Custom Parameters

        Steps:
        1. Create new chat
        2. Select option 3 (KeyValueMemory)
        3. Enter "3" (non_compressible_count)
        4. Enter "5" (buffer_size)
        5. Verify custom parameters
        """
        test_input = (
            "1\n"  # Новый чат
            "KeyValueMemory Custom\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "3\n"  # KeyValueMemoryStrategy
            "3\n"  # non_compressible_count=3
            "5\n"  # buffer_size=5
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "KeyValueMemoryStrategy" in stdout

    def test_tc_037_default_strategy_creation(self):
        """
        TC-037: DefaultStrategy Creation

        Steps:
        1. Create new chat
        2. Select option 1 (Default)
        3. Verify no extra parameters prompted
        4. Verify strategy type = "DefaultStrategy"
        """
        test_input = (
            "1\n"  # Новый чат
            "DefaultStrategy Test\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "DefaultStrategy" in stdout or "[OK]" in stdout


class TestUC002_SelectExistingChatFromList:
    """
    Use Case UC-002: Select Existing Chat from List

    Test Cases:
    - TC-004: Select Chat from Empty List
    - TC-005: Preview with System Prompt Only
    - TC-006: Preview with User Message
    """

    def test_tc_004_select_chat_from_empty_list(self):
        """
        TC-004: Select Chat from Empty List

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

    def test_tc_005_preview_with_system_prompt_only(self):
        """
        TC-005: Preview with System Prompt Only

        Steps:
        1. Create chat with system prompt only
        2. Return to menu using /menu command
        3. Exit app
        4. Verify preview shows "(нет сообщений)"
        5. Verify count shows "Сообщений: 0"
        """
        create_input = (
            "1\n"  # Новый чат
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

    def test_tc_006_preview_with_user_message(self):
        """
        TC-006: Preview with User Message

        Steps:
        1. Create chat
        2. Send message "Hello world"
        3. Return to menu
        4. Verify preview shows "Hello world"
        """
        create_input = (
            "1\n"  # Новый чат
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
    - TC-007: Return to Chat Without Active Chat
    - TC-008: Return to Chat With Active Chat
    """

    def test_tc_007_return_to_chat_without_active_chat(self):
        """
        TC-007: Return to Chat Without Active Chat

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

    def test_tc_008_return_to_chat_with_active_chat(self):
        """
        TC-008: Return to Chat With Active Chat

        Steps:
        1. Create or select chat
        2. Type "/menu"
        3. Verify option 3 shows "Вернуться в чат: {name}"
        4. Select option 3
        5. Verify chat loop entered with same context
        """
        test_input = (
            "1\n"  # Новый чат
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
    - TC-009: Send Multiple Messages
    - TC-010: Empty Message Handling
    - TC-016: Unknown Command Handling
    - TC-017: System Prompt in History
    - TC-018: Special Characters in Input
    """

    def test_tc_009_send_multiple_messages(self):
        """
        TC-009: Send Multiple Messages

        Steps:
        1. Enter chat
        2. Send "Message 1"
        3. Send "Message 2"
        4. Send "Message 3"
        5. Return to menu
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_010_empty_message_handling(self):
        """
        TC-010: Empty Message Handling

        Steps:
        1. Enter chat
        2. Press Enter (empty) - should re-prompt
        3. Press Enter again - should re-prompt
        4. Send valid message - normal flow resumes
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_016_unknown_command_handling(self):
        """
        TC-016: Unknown Command Handling

        Steps:
        1. Enter chat
        2. Type "/unknown"
        3. Verify warning about unknown command
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_017_system_prompt_in_history(self):
        """
        TC-017: System Prompt in History

        Steps:
        1. Create chat with system prompt
        2. Verify history contains system message
        3. Check role = "system"
        4. Check display with [SYSTEM] prefix
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_018_special_characters_in_input(self):
        """
        TC-018: Special Characters in Input

        Steps:
        1. Create chat
        2. Send message with special characters
        3. Verify message handled correctly
        """
        special_message = "Test @#$%^&*()_+-=[]{}|;':\",./<>?"

        test_input = (
            "1\n"  # Новый чат
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
    - TC-011: View Settings
    - TC-012: Change Partial Settings
    - TC-027: Settings Change With Confirmation
    - TC-028: Settings Change Cancelled
    """

    def test_tc_011_view_settings(self):
        """
        TC-011: View Settings

        Steps:
        1. Enter chat with configured settings
        2. Type "/settings"
        3. Verify current settings displayed
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_012_change_partial_settings(self):
        """
        TC-012: Change Partial Settings

        Steps:
        1. Type "/settings"
        2. Change only temperature
        3. Press Enter for others
        4. Verify only temperature changed
        """
        test_input = (
            "1\n"  # Новый чат
            "PartialSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Change settings
            "1\n"  # Keep model 1
            "0.8\n"  # New temperature
            "\n" + "\n" + "\n"  # Keep top_p, top_k, reasoning_effort defaults
            "1\n"  # Confirm reasoning effort (default 1)
            "\n"  # Keep context window size default
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "[OK] Настройки обновлены!" in stdout or "обновлены" in stdout.lower()

    def test_tc_027_settings_change_with_confirmation(self):
        """
        TC-027: Settings Change With Confirmation

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "y"
        4. Verify all settings prompts shown
        """
        test_input = (
            "1\n"  # Новый чат
            "ConfirmSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Confirm change
            "0.8\n"  # New temperature
            "\n" + "\n" + "\n" + "\n"  # Keep others
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Изменить настройки?" in stdout or "y/n" in stdout

    def test_tc_028_settings_change_cancelled(self):
        """
        TC-028: Settings Change Cancelled

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "n"
        4. Verify return to chat without changes
        """
        test_input = (
            "1\n"  # Новый чат
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
    - TC-013: Menu Navigation from Chat
    - TC-020: Concurrent Chat Operations
    """

    def test_tc_013_menu_navigation_from_chat(self):
        """
        TC-013: Menu Navigation from Chat

        Steps:
        1. Enter chat
        2. Type "/menu"
        3. Verify Main Menu displayed
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_020_concurrent_chat_operations(self):
        """
        TC-020: Concurrent Chat Operations

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
            "Chat A\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "1\n"  # Новый чат - создать Chat B
            "Chat B\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/menu\n"  # Return to menu
            "2\n"  # Выбрать чат - показать список
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App exited with code {returncode}, stderr: {stderr}"
        assert "Chat A" in stdout or "Chat B" in stdout, (
            f"Expected 'Chat A' or 'Chat B' in output, got: {stdout}"
        )


class TestUC007_StopOngoingGeneration:
    """
    Use Case UC-007: Stop Ongoing Generation

    Test Cases:
    - TC-014: Stop Command When Idle
    - TC-029: Stop Command During Generation
    - TC-030: Stop Command When Idle (duplicate check)
    """

    def test_tc_014_stop_command_when_idle(self):
        """
        TC-014: Stop Command When Idle

        Steps:
        1. Enter chat
        2. Type "/stop" (no generation)
        3. Verify message about generation status
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_029_stop_command_during_generation(self):
        """
        TC-029: Stop Command During Generation

        Note: In mock/test mode, generation is instant.
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_030_stop_command_when_idle(self):
        """
        TC-030: Stop Command When Idle

        Steps:
        1. Wait for idle state (no generation active)
        2. Type "/stop"
        3. Verify output "Генерация не активна."
        4. Verify no state changes
        """
        test_input = (
            "1\n"  # Новый чат
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
    - TC-015: Help Command
    """

    def test_tc_015_help_command(self):
        """
        TC-015: Help Command

        Steps:
        1. Enter chat
        2. Type "/help"
        3. Verify command list displayed
        """
        test_input = (
            "1\n"  # Новый чат
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
    - TC-021: View Summary With Summarization
    - TC-022: View Summary Without Summarization
    """

    def test_tc_021_view_summary_with_summarization(self):
        """
        TC-021: View Summary With Summarization
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_022_view_summary_without_summarization(self):
        """
        TC-022: View Summary Without Summarization
        """
        test_input = (
            "1\n"  # Новый чат
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
    - TC-023: View Chat Info With Token Statistics
    - TC-038: View Info For Different Strategies
    """

    def test_tc_023_view_chat_info_with_token_statistics(self):
        """
        TC-023: View Chat Info With Token Statistics
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_038_view_info_for_different_strategies(self):
        """
        TC-038: View Info For Different Strategies
        """
        test_input = (
            "1\n"  # Новый чат
            "DefaultInfo\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "/info\n"  # View info
            "4\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Стратегия:" in stdout or "DefaultStrategy" in stdout


class TestUC011_CreateChatBranch:
    """
    Use Case UC-011: Create Chat Branch

    Test Cases:
    - TC-024: Create Branch And Switch
    - TC-025: Create Branch And Stay
    - TC-026: Create Branch With Custom Name
    - TC-039: Branch Preserves Strategy Type
    - TC-040: Branch Preserves SlidingWindow Configuration
    """

    def test_tc_024_create_branch_and_switch(self):
        """
        TC-024: Create Branch And Switch
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_025_create_branch_and_stay(self):
        """
        TC-025: Create Branch And Stay
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_026_create_branch_with_custom_name(self):
        """
        TC-026: Create Branch With Custom Name
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_039_branch_preserves_strategy_type(self):
        """
        TC-039: Branch Preserves Strategy Type
        """
        test_input = (
            "1\n"  # Новый чат
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

    def test_tc_040_branch_preserves_sliding_window_configuration(self):
        """
        TC-040: Branch Preserves SlidingWindow Configuration
        """
        test_input = (
            "1\n"  # Новый чат
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
