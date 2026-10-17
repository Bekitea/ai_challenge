"""Загрузчик расширения sqlite-vec (vec0) для SQLite.

Бинарники вендорятся рядом с этим модулем и выбираются по платформе:
``vec0.so`` для Linux/musl и ``vec0.dll`` для Windows (win_amd64).

Почему не PyPI-пакет ``sqlite-vec``: на Alpine/musl нет подходящего
колеса и нет sdist, поэтому ``pip install sqlite-vec`` там не работает.
Подробности — в ``INSTALL.md`` рядом с этим файлом.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["is_available", "load", "loadable_path"]


def _binary_file() -> Path:
    """Возвращает путь к вендорному бинарнику для текущей платформы."""
    base = Path(__file__).resolve().parent
    return base / ("vec0.dll" if sys.platform == "win32" else "vec0.so")


def loadable_path() -> str:
    """Путь к расширению без суффикса.

    SQLite сам дописывает платформенный суффикс (``.so``/``.dll``), поэтому
    такой путь одинаково работает на Linux и Windows.
    """
    return str(_binary_file().with_suffix(""))


def is_available() -> bool:
    """Проверяет, есть ли вендорный бинарник для текущей платформы."""
    return _binary_file().is_file()


def load(connection) -> None:
    """Загружает расширение sqlite-vec в указанное соединение SQLite.

    Args:
        connection: DBAPI-соединение sqlite3 (например, из SQLAlchemy).
    """
    connection.enable_load_extension(True)
    try:
        connection.load_extension(loadable_path())
    finally:
        connection.enable_load_extension(False)
