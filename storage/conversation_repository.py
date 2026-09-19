import pickle
from pathlib import Path

from agents import Prompt
from config import FILE_STORAGE_DIR


class ConversationRepository:
    """
    Инкапсулирует логику сохранения и загрузки истории сообщений из файлов.

    Файлы хранятся в директории, указанной в config.FILE_STORAGE_DIR.
    Имя файла: {conversation_id}.pkl
    Содержимое: список объектов Prompt, сериализованный через pickle.
    """

    def __init__(self, storage_dir: str | None = None):
        """
        Инициализирует хранилище.

        Args:
            storage_dir: Путь к директории для хранения файлов.
                         По умолчанию используется config.FILE_STORAGE_DIR.
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path(FILE_STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, conversation_id: str) -> Path:
        """Возвращает путь к файлу истории для данного агента."""
        return self.storage_dir / f"{conversation_id}.pkl"

    def save_history(self, conversation_id: str, history: list[Prompt]) -> None:
        """
        Сохраняет историю сообщений в файл.

        Args:
            conversation_id: UUID.
            history: Список объектов Prompt для сохранения.
        """
        file_path = self._get_file_path(conversation_id)
        with open(file_path, "wb") as f:
            pickle.dump(history, f)

    def load_history(self, conversation_id: str) -> list[Prompt]:
        """
        Загружает историю сообщений из файла.

        Args:
            conversation_id: UUID.

        Returns:
            Список объектов Prompt. Пустой список, если файл не найден.
        """
        file_path = self._get_file_path(conversation_id)
        if not file_path.exists():
            return []

        with open(file_path, "rb") as f:
            return pickle.load(f)

    def delete_history(self, conversation_id: str) -> None:
        """
        Удаляет файл истории для данного агента.

        Args:
            conversation_id: UUID.
        """
        file_path = self._get_file_path(conversation_id)
        if file_path.exists():
            file_path.unlink()

    def history_exists(self, conversation_id: str) -> bool:
        """
        Проверяет, существует ли файл истории для данного агента.

        Args:
            conversation_id: UUID.

        Returns:
            True, если файл существует, иначе False.
        """
        return self._get_file_path(conversation_id).exists()
