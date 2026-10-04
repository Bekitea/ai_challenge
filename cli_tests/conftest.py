"""Общие pytest-фикстуры для e2e-тестов CLI."""

import os

# ВАЖНО: Установить APPLICATION_MODE ДО импорта любых модулей проекта,
# так как config.py читает эту переменную при загрузке модуля
os.environ["APPLICATION_MODE"] = "TEST"

# Из контейнера Ollama доступна только через host.docker.internal, а не через
# устаревший docker.internal (он не резолвится). Нормализуем URL для тестов.
if os.path.exists("/.dockerenv"):
    os.environ["OLLAMA_BASE_URL"] = os.environ.get(
        "OLLAMA_BASE_URL", ""
    ).replace("http://docker.internal", "http://host.docker.internal:11434") or (
        "http://host.docker.internal:11434"
    )

import sys

import pytest
from e2e_helpers import clean_test_data, get_project_root


@pytest.fixture(autouse=True)
def setup_clean_test_environment():
    """Автоматически очищает тестовые данные и инициализирует БД перед каждым тестом."""
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
