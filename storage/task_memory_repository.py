"""Хранилище памяти задачи текущего диалога.

Память задачи хранится per-chat (по ``conversation_id``) в pickle-файлах,
по аналогии с фактами профилей задач и глобальной памятью. Она не связана
с профилем задачи и живёт ровно столько, сколько существует диалог.
"""

from __future__ import annotations

import pickle
from abc import ABC, abstractmethod
from pathlib import Path

from agents import TaskMemory


class TaskMemoryRepository(ABC):
    """Абстрактное хранилище памяти задачи диалога."""

    @abstractmethod
    def get_memory(self, conversation_id: str) -> TaskMemory | None:
        """Возвращает память задачи диалога или None, если её нет."""
        ...

    @abstractmethod
    def save_memory(self, conversation_id: str, memory: TaskMemory) -> None:
        """Сохраняет память задачи диалога."""
        ...

    @abstractmethod
    def delete_memory(self, conversation_id: str) -> None:
        """Удаляет память задачи диалога."""
        ...


class FileTaskMemoryRepository(TaskMemoryRepository):
    """Файловое хранилище памяти задачи (pickle по conversation_id)."""

    def __init__(self, base_dir: str):
        """
        Инициализирует репозиторий.

        Args:
            base_dir: Базовая директория файлового хранилища приложения.
        """
        self._dir = Path(base_dir) / "task_memory"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, conversation_id: str) -> Path:
        """Возвращает путь к файлу памяти диалога."""
        return self._dir / f"{conversation_id}.pkl"

    def get_memory(self, conversation_id: str) -> TaskMemory | None:
        """Загружает память задачи из файла (устойчиво к битым файлам)."""
        path = self._get_path(conversation_id)
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                memory = pickle.load(f)
        except (pickle.UnpicklingError, EOFError, AttributeError, ValueError):
            return None
        return memory if isinstance(memory, TaskMemory) else None

    def save_memory(self, conversation_id: str, memory: TaskMemory) -> None:
        """Сохраняет память задачи в файл."""
        with open(self._get_path(conversation_id), "wb") as f:
            pickle.dump(memory, f)

    def delete_memory(self, conversation_id: str) -> None:
        """Удаляет файл памяти задачи, если он существует."""
        path = self._get_path(conversation_id)
        if path.exists():
            path.unlink()
