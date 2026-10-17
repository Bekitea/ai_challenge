"""Общие pytest-фикстуры для e2e-тестов CLI."""

import os
import shutil
import sys
import time

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

import pytest
from e2e_helpers import (
    clean_test_data,
    get_project_root,
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
