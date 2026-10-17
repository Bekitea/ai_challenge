"""Общие pytest-фикстуры для e2e-тестов CLI.

Общая инициализация (``APPLICATION_MODE``, ``AI_CHAT_TEST_DATA_DIR``, session-
хуки очистки) живёт в родительском ``core/tests/conftest.py``. Здесь остаётся
только специфика e2e-набора CLI.
"""

import os
import sys

import pytest

# Из контейнера Ollama доступна только через host.docker.internal, а не через
# устаревший docker.internal (он не резолвится). Нормализуем URL для тестов.
if os.path.exists("/.dockerenv"):
    os.environ["OLLAMA_BASE_URL"] = os.environ.get(
        "OLLAMA_BASE_URL", ""
    ).replace("http://docker.internal", "http://host.docker.internal:11434") or (
        "http://host.docker.internal:11434"
    )

from e2e_helpers import clean_test_data, get_project_root


@pytest.fixture(autouse=True)
def setup_clean_test_environment():
    """Автоматически очищает тестовые данные и инициализирует БД перед каждым тестом."""
    clean_test_data()

    # Initialize database
    sys.path.insert(0, str(get_project_root()))
    from core.infrastructure.persistence.db_connection import DatabaseConnection
    from core.infrastructure.persistence.orm import Base

    db = DatabaseConnection(connect_args={"check_same_thread": False, "timeout": 30})
    db.init_tables(Base.metadata)
    # Явно закрываем соединение, чтобы освободить файл БД для subprocess на Windows
    db.close()

    yield
    # Optional: cleanup after test as well
    # clean_test_data()
