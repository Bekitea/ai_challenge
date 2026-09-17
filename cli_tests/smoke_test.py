#!/usr/bin/env python3
"""
Smoke test for CLI chat application.
Tests basic interaction with the mock provider in test mode.
"""

import os

# ВАЖНО: Установить APPLICATION_MODE ДО импорта любых модулей проекта,
# так как config.py читает эту переменную при загрузке модуля
os.environ["APPLICATION_MODE"] = "TEST"

import subprocess
import sys
from pathlib import Path

# Add project root to path to import modules
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from storage.agent_repositories import PersistentAgentRepository


def run_smoke_test():
    """Run basic smoke test scenario in test mode."""

    # Test input:
    # 1 - Новый чат
    # "Test Chat" - имя чата
    # "" - системный промпт (пропуск)
    # 1 - модель GPT OSS 120B
    # "" - температура (отключена)
    # "" - top P (отключен)
    # "" - top K (0 по умолчанию)
    # "" - reasoning effort (1 none по умолчанию)
    # "" - контекстное окно (200k по умолчанию)
    # 1 - стратегия Default
    # "" - параметры стратегии (по умолчанию)
    # "Hello, how are you?" - сообщение пользователю
    # 0 - выход из чата
    # 4 - выход из приложения
    test_input = "1\nTest Chat\n\n1\n\n\n\n\n\n1\n\n\nHello, how are you?\n0\n4\n"

    print("Running smoke test in TEST MODE (APPLICATION_MODE=TEST)...")
    print(f"Test input:\n{test_input!r}")
    print("-" * 50)

    try:
        # Очищаем тестовую директорию
        import shutil

        test_data_dir = project_root / "test-data"
        if test_data_dir.exists():
            shutil.rmtree(test_data_dir)
        test_data_dir.mkdir(parents=True, exist_ok=True)

        # Устанавливаем переменную окружения для тестового режима
        env = os.environ.copy()
        env["APPLICATION_MODE"] = "TEST"

        # Инициализируем базу данных через репозиторий с mock провайдером
        # Используем тот же путь к БД, который будет использоваться приложением
        from llm_providers import MockLlmProvider

        repo = PersistentAgentRepository(llm_provider=MockLlmProvider())
        repo.init_db()
        print("✓ Test database initialized")

        # Run the CLI application with APPLICATION_MODE=TEST for mock provider
        process = subprocess.Popen(
            [sys.executable, "main_cli.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
            env=env,  # Передаем переменные окружения с APPLICATION_MODE=TEST
        )

        stdout, stderr = process.communicate(input=test_input, timeout=30)

        print("STDOUT:")
        print(stdout)
        print("-" * 50)

        if stderr:
            print("STDERR:")
            print(stderr)
            print("-" * 50)

        # Check if the output contains expected elements
        success = True

        # Check for menu display
        if "МЕНЮ" not in stdout and "1. Новый чат" not in stdout:
            print("❌ Menu not displayed correctly")
            success = False
        else:
            print("✓ Menu displayed correctly")

        # Check for model selection
        if "Выберите модель" not in stdout and "Select model" not in stdout:
            print("⚠ Model selection not found (may be OK depending on flow)")
        else:
            print("✓ Model selection displayed")

        # Verify mock provider is being used (check for mock responses)
        if "[MOCK" in stdout or "[MOCK RESPONSE]" in stdout:
            print("✓ Mock provider is being used (expected in test mode)")
        elif "MODEL_RESPONSE" in stdout or "mock response" in stdout.lower():
            print("✓ Mock provider responded successfully")
        else:
            print("⚠ Could not verify mock provider usage (may still be working)")

        # Check if application processed user message
        if "Hello, how are you?" in stdout:
            print("✓ User message was echoed/displayed")

        # Check for assistant response (mock provider should respond)
        # Mock provider returns: [MOCK RESPONSE] Это тестовый ответ на ваш запрос: '...'
        if "[MOCK RESPONSE]" in stdout or "тестовый ответ" in stdout.lower():
            print("✓ Mock provider responded with expected format")
        elif "assistant" in stdout.lower() or "ответ" in stdout.lower():
            print("✓ Assistant response received")

        # Check exit code
        if process.returncode == 0:
            print("✓ Application exited with code 0")
        else:
            print(f"❌ Application exited with code {process.returncode}")
            success = False

        # Show stderr if present (should be empty in test mode)
        if stderr and "ERROR" in stderr.upper():
            print(f"⚠ Unexpected errors in stderr:\n{stderr}")
            success = False
        elif stderr.strip():
            print(f"ℹ Stderr output (non-critical):\n{stderr}")
        else:
            print("✓ No errors in stderr")

        print("-" * 50)
        if success:
            print("✅ Smoke test PASSED")
            return True
        else:
            print("❌ Smoke test FAILED")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        process.kill()
        return False
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
