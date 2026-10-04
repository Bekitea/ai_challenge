"""Переиспользуемые части e2e-тестов CLI.

Модуль не импортирует модули проекта на уровне модуля, поэтому его можно
безопасно импортировать до установки APPLICATION_MODE.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Быстрое создание чата: меню -> 1 -> Enter (default "n") -> цикл чата.
_QUICK_CHAT = "1\n\n"

# Ручное создание с дефолтными настройками и DefaultStrategy.
_MANUAL_DEFAULTS = (
    "1\n"  # Новый чат
    + "y\n"  # Хотите настроить?
)


def _manual_chat(name: str) -> str:
    """Шаги ручного создания чата с указанным именем и прочими дефолтами."""
    return (
        _MANUAL_DEFAULTS
        + f"{name}\n"
        + "\n"  # Системный промпт (пропуск)
        + "\n" * 6  # Модель/temp/top_p/top_k/reasoning/context — дефолты
        + "1\n"  # DefaultStrategy
        # Профилей нет => блок привязки профиля пропускается без ввода.
    )


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


def run_cli_command(
    test_input: str,
    timeout: int = 30,
) -> tuple[str, str, int]:
    """
    Run CLI application with given input and return output.

    This function simulates real user interaction by:
    1. Spawning actual subprocess
    2. Sending input via stdin (like real keyboard input)
    3. Capturing stdout/stderr (like real terminal output)

    Функция сама проверяет инварианты успешного запуска: код возврата равен
    0, а stderr пуст. Поэтому в тестах эти проверки дублировать не нужно, а
    неиспользуемые части результата можно отбрасывать через `_`.

    Args:
        test_input: String with newlines representing user keystrokes
        timeout: Maximum execution time in seconds

    Returns:
        Tuple of (stdout, stderr, return_code)

    Raises:
        AssertionError: Если процесс завершился с ненулевым кодом или записал
            что-либо в stderr.
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

    assert process.returncode == 0, (
        f"CLI exited with code {process.returncode}\n"
        f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    )
    assert stderr == "", (
        f"stderr must be empty on success, got:\n{stderr}\n"
        f"--- stdout ---\n{stdout}"
    )
    return stdout, stderr, process.returncode
