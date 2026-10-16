"""Переиспользуемые части e2e-тестов CLI.

Модуль не импортирует модули проекта на уровне модуля, поэтому его можно
безопасно импортировать до установки APPLICATION_MODE.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Быстрое создание чата: меню -> 1 -> Enter (default "n") -> выбор модели (3)
# -> Enter (reasoning effort, default "none").
# Модель и reasoning effort обязательны, поэтому их ввод всегда присутствует.
_QUICK_CHAT = "1\n\n3\n\n"

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
        + "3\n"  # Модель (Alice AI LLM Flash, yandex)
        + "\n" * 6  # temp/top_p/top_k/max_tokens/reasoning/context — дефолты
        + "1\n"  # DefaultStrategy
        # Профилей нет => блок привязки профиля пропускается без ввода.
    )


def _resolve_test_data_dir_name() -> str:
    """Имя директории тестового хранилища с учётом воркера pytest-xdist.

    При параллельном прогоне каждый воркер пишет в свою директорию, иначе
    subprocess'ы из разных тестов затирали бы БД и файловое хранилище друг
    друга.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    return f"test-data-{worker}" if worker else "test-data"


TEST_DATA_DIR_NAME = _resolve_test_data_dir_name()

# config.py читает этот путь при импорте. В воркере xdist значение обязательно
# перезаписываем: контроллер экспортирует `AI_CHAT_TEST_DATA_DIR=./test-data`,
# и без перезаписи воркер унаследовал бы общий каталог (fixture писал бы в
# `test-data`, а subprocess — в `test-data-<worker>`). В serial-режиме
# `setdefault` позволяет вручную задать каталог для отладки.
if os.environ.get("PYTEST_XDIST_WORKER"):
    os.environ["AI_CHAT_TEST_DATA_DIR"] = f"./{TEST_DATA_DIR_NAME}"
else:
    os.environ.setdefault("AI_CHAT_TEST_DATA_DIR", f"./{TEST_DATA_DIR_NAME}")


def ollama_available(timeout: float = 3.0) -> bool:
    """Проверяет доступность Ollama (эмбеддинги RAG требуют реальной модели)."""
    import urllib.error
    import urllib.request

    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def get_project_root() -> Path:
    """Dynamically resolve project root directory."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent


def get_test_data_path() -> Path:
    """Get path to test data directory (изолированную для текущего воркера)."""
    return get_project_root() / TEST_DATA_DIR_NAME


def clean_test_data():
    """Clean test data directory before and after each test."""
    test_data_path = get_test_data_path()
    if test_data_path.exists():
        shutil.rmtree(test_data_path)
    test_data_path.mkdir(parents=True, exist_ok=True)


def list_test_data_dirs() -> list[Path]:
    """Возвращает все каталоги ``test-data*`` в корне проекта.

    Включает как ``test-data`` (serial-прогон), так и ``test-data-<worker>``
    (pytest-xdist), в том числе «осиротевшие» от прошлых упавших прогонов.
    """
    return [path for path in get_project_root().glob("test-data*") if path.is_dir()]


def remove_all_test_data():
    """Удаляет все каталоги ``test-data*`` в корне проекта."""
    for path in list_test_data_dirs():
        shutil.rmtree(path, ignore_errors=True)


def mock_llm(
    responses: list[dict] | None = None,
    default: dict | None = None,
    json_object: dict | None = None,
) -> dict:
    """Собирает описание сценария мока LLM для ``run_cli_command``.

    Args:
        responses: Список ответов, выдаваемых по порядку (каждый — dict с
            ``content``/``reasoning``/``prompt_tokens``/``completion_tokens``/
            ``tool_calls`` или ``error``).
        default: Ответ, используемый после исчерпания ``responses``.
        json_object: Ответ при запросе с ``response_format=json_object``.

    Returns:
        dict: сценарий для передачи в аргумент ``mock``.
    """
    scenario: dict = {}
    if responses is not None:
        scenario["responses"] = responses
    if default is not None:
        scenario["default"] = default
    if json_object is not None:
        scenario["json_object"] = json_object
    return scenario


def run_cli_command(
    test_input: str,
    timeout: int = 30,
    env: dict | None = None,
    mock: dict | str | None = None,
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
        env: Дополнительные переменные окружения для subprocess.
        mock: Сценарий мока LLM (dict или готовая JSON-строка) — передаётся
            приложению через ``MOCK_LLM_SCENARIO``.

    Returns:
        Tuple of (stdout, stderr, return_code)

    Raises:
        AssertionError: Если процесс завершился с ненулевым кодом или записал
            что-либо в stderr.
    """
    project_root = get_project_root()

    # Устанавливаем переменную окружения для тестового режима
    process_env = os.environ.copy()
    process_env["APPLICATION_MODE"] = "TEST"
    process_env["AI_CHAT_TEST_DATA_DIR"] = f"./{TEST_DATA_DIR_NAME}"
    if mock is not None:
        process_env["MOCK_LLM_SCENARIO"] = (
            mock if isinstance(mock, str) else json.dumps(mock, ensure_ascii=False)
        )
    if env:
        process_env.update(env)

    process = subprocess.Popen(
        [sys.executable, "main_cli.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(project_root),
        env=process_env,
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
