"""Общие pytest-фикстуры для тестов REST API."""

import os
import shutil
import sys
import time
from pathlib import Path

# ВАЖНО: APPLICATION_MODE должен быть установлен до импорта модулей проекта,
# так как config.py читает его при загрузке.
os.environ["APPLICATION_MODE"] = "TEST"

# Изоляция хранилища по воркерам pytest-xdist (иначе параллельные воркеры
# пишут в общий test-data и мешают друг другу). В воркере перезаписываем
# значение: контроллер экспортирует AI_CHAT_TEST_DATA_DIR=./test-data, и
# setdefault оставил бы воркер без собственного каталога.
_WORKER = os.environ.get("PYTEST_XDIST_WORKER")
_TEST_DATA_DIR_NAME = f"test-data-{_WORKER}" if _WORKER else "test-data"
if _WORKER:
    os.environ["AI_CHAT_TEST_DATA_DIR"] = f"./{_TEST_DATA_DIR_NAME}"
else:
    os.environ.setdefault("AI_CHAT_TEST_DATA_DIR", f"./{_TEST_DATA_DIR_NAME}")

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / _TEST_DATA_DIR_NAME

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "cli_tests") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "cli_tests"))

from e2e_helpers import list_test_data_dirs, remove_all_test_data

_SESSION_START = time.time()


def pytest_sessionstart(session):
    """Убирает осиротевшие каталоги ``test-data*`` от прошлых прогонов.

    Выполняется только на контроллере (без ``PYTEST_XDIST_WORKER``) и удаляет
    лишь каталоги, созданные до старта текущей сессии.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    for path in list_test_data_dirs():
        try:
            if path.stat().st_mtime < _SESSION_START:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def pytest_sessionfinish(session, exitstatus):
    """Удаляет каталоги ``test-data*`` после успешного прогона.

    При падении данные сохраняются для разбора.
    """
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    if exitstatus == 0:
        remove_all_test_data()


def _clean_test_data() -> None:
    """Полностью очищает изолированное тестовое хранилище и создаёт заново.

    Каталог пересоздаётся сразу: `config.py` создаёт директории только при
    первом импорте, а в общем прогоне он уже импортирован (например, CLI-fixture),
    поэтому без mkdir SQLite не сможет открыть БД.
    """
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Автоматически очищает тестовые данные перед каждым тестом."""
    _clean_test_data()
    yield


@pytest.fixture()
def app():
    """Собирает приложение и возвращает пару (app, use_cases)."""
    from api.app import build_app
    from app_factory import initialize_application

    use_cases = initialize_application()
    return build_app(use_cases), use_cases


@pytest.fixture()
def client(app):
    """TestClient с действующим API-ключом в заголовке по умолчанию."""
    application, use_cases = app
    with TestClient(application) as test_client:
        created = use_cases.create_api_key.execute("pytest")
        test_client.headers["Authorization"] = f"Bearer {created.api_key}"
        yield test_client


@pytest.fixture()
def anon_client(app):
    """TestClient без API-ключа (для проверок авторизации)."""
    application, _ = app
    with TestClient(application) as test_client:
        yield test_client
