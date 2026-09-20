import pickle
from abc import ABC, abstractmethod
from pathlib import Path

from agents import GlobalMemory


class GlobalMemoryRepository(ABC):
    """Абстракция для хранения и управления глобальной памятью."""

    @abstractmethod
    def get_memory(self) -> GlobalMemory:
        """
        Получает глобальную память.

        Returns:
            GlobalMemory: Экземпляр глобальной памяти.
        """

    @abstractmethod
    def save_memory(self, memory: GlobalMemory) -> None:
        """
        Сохраняет глобальную память.

        Args:
            memory: Глобальная память для сохранения.
        """


class FileGlobalMemoryRepository(GlobalMemoryRepository):
    """
    Реализация GlobalMemoryRepository с хранением в файле.

    Глобальная память сериализуется через pickle и сохраняется в файл.
    """

    def __init__(self, memory_path: str):
        """
        Инициализирует репозиторий.

        Args:
            memory_path: Путь к файлу хранения глобальной памяти.
        """
        self._memory_path = Path(memory_path)

    def get_memory(self) -> GlobalMemory:
        """
        Загружает глобальную память из файла.

        Returns:
            GlobalMemory: Экземпляр глобальной памяти.
        """
        if not self._memory_path.exists():
            return GlobalMemory()

        try:
            with open(self._memory_path, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError, AttributeError):
            # При ошибке десериализации возвращаем пустую память
            return GlobalMemory()

    def save_memory(self, memory: GlobalMemory) -> None:
        """
        Сохраняет глобальную память в файл.

        Args:
            memory: Глобальная память для сохранения.
        """
        # Создаём директорию если она не существует
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self._memory_path, "wb") as f:
            pickle.dump(memory, f)
