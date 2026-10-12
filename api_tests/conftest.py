"""Общие pytest-фикстуры для тестов REST API."""

import os
import shutil
import sys
from pathlib import Path

# ВАЖНО: APPLICATION_MODE должен быть установлен до импорта модулей проекта,
# так как config.py читает его при загрузке.
os.environ["APPLICATION_MODE"] = "TEST"

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test-data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _clean_test_data() -> None:
    """Полностью очищает изолированное тестовое хранилище."""
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Автоматически очищает тестовые данные перед каждым тестом."""
    _clean_test_data()
    yield


@pytest.fixture()
def client():
    """Возвращает TestClient поверх приложения в тестовом режиме."""
    from api.app import build_app
    from app_factory import initialize_application

    use_cases = initialize_application()
    app = build_app(use_cases)
    with TestClient(app) as test_client:
        yield test_client
