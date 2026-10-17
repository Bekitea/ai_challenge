"""Общие pytest-фикстуры для тестов REST API.

Общая инициализация (``APPLICATION_MODE``, ``AI_CHAT_TEST_DATA_DIR``, session-
хуки очистки) живёт в родительском ``core/tests/conftest.py``.
"""

import shutil
from contextlib import suppress

import pytest
from e2e_helpers import get_test_data_path
from fastapi.testclient import TestClient


def _clean_test_data() -> None:
    """Полностью очищает изолированное тестовое хранилище и создаёт заново.

    Каталог пересоздаётся сразу: `config.py` создаёт директории только при
    первом импорте, а в общем прогоне он уже импортирован (например, CLI-fixture),
    поэтому без mkdir SQLite не сможет открыть БД.
    """
    test_data_dir = get_test_data_path()
    shutil.rmtree(test_data_dir, ignore_errors=True)
    test_data_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Автоматически очищает тестовые данные перед каждым тестом."""
    _clean_test_data()
    yield


def _dispose_db(use_cases) -> None:
    """Освобождает SQLite-соединения после API-теста.

    ``initialize_application()`` открывает SQLAlchemy-engine; на Windows он
    держит файл ``agents.db`` и мешает следующему CLI-тесту в том же воркере
    xdist очистить ``test-data-<worker>/`` (``WinError 32``). Достаём
    ``DatabaseConnection`` через фабрику сессий репозитория и закрываем пул.
    """
    with suppress(Exception):
        repository = use_cases.create_chat.repository
        db_connection = getattr(repository._session_factory, "__self__", None)
        if db_connection is not None:
            db_connection.close()


@pytest.fixture()
def app():
    """Собирает приложение и возвращает пару (app, use_cases)."""
    from core.di.app_factory import initialize_application
    from core.presentation.api.app import build_app

    use_cases = initialize_application()
    try:
        yield build_app(use_cases), use_cases
    finally:
        _dispose_db(use_cases)


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
