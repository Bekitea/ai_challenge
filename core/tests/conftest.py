"""Общая настройка тестового окружения для всех тестов под ``core/tests/``.

Этот conftest загружается pytest для всех тестов проекта и выполняет общую
инициализацию, которая не зависит от конкретного набора тестов (CLI, API,
core):

- включает ``APPLICATION_MODE=TEST`` до импорта модулей проекта (``config.py``
  читает эту переменную при загрузке);
- настраивает изоляцию хранилища по воркерам ``pytest-xdist`` через
  ``AI_CHAT_TEST_DATA_DIR`` (см. :mod:`e2e_helpers`);
- добавляет в ``sys.path`` корень проекта и каталог общей инфраструктуры;
- владеет session-хуками очистки «осиротевших» каталогов ``test-data*``.

Специфика конкретных наборов (например, autouse-очистка БД для e2e или
фикстуры ``app``/``client`` для REST API) живёт в conftest соответствующего
подкаталога.
"""

import os
import sys
import time
from pathlib import Path

# ВАЖНО: APPLICATION_MODE должен быть установлен до импорта модулей проекта,
# так как config.py читает его при загрузке.
os.environ["APPLICATION_MODE"] = "TEST"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

# Импорт настраивает AI_CHAT_TEST_DATA_DIR (worker-aware) как побочный эффект.
from e2e_helpers import (
    list_test_data_dirs,
    remove_all_test_data,
)

_SESSION_START = time.time()


def pytest_sessionstart(session):
    """Убирает осиротевшие каталоги ``test-data*`` от прошлых прогонов.

    Выполняется только на контроллере (без ``PYTEST_XDIST_WORKER``) и удаляет
    лишь каталоги, созданные до старта текущей сессии, чтобы не задеть
    директории параллельных воркеров.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    import shutil

    for path in list_test_data_dirs():
        try:
            if path.stat().st_mtime < _SESSION_START:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def pytest_sessionfinish(session, exitstatus):
    """Удаляет каталоги ``test-data*`` после успешного прогона.

    При падении (``exitstatus != 0``) данные сохраняются для разбора. На
    контроллере xdist ``exitstatus`` агрегированный, поэтому очистка не
    затрёт артефакты упавшего воркера.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    if exitstatus == 0:
        remove_all_test_data()
