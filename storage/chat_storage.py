import pickle
from pathlib import Path

from agents import Prompt
from config import FILE_STORAGE_DIR


class ChatHistoryStorage:
    """
    Инкапсулирует логику сохранения и загрузки истории сообщений из файлов.

    Файлы хранятся в директории, указанной в config.CHAT_HISTORY_DIR.
    Имя файла: {agent_id}.pkl
    Содержимое: список объектов Prompt, сериализованный через pickle.
    """

    def __init__(self, storage_dir: str | None = None):
        """
        Инициализирует хранилище.

        Args:
            storage_dir: Путь к директории для хранения файлов.
                         По умолчанию используется config.CHAT_HISTORY_DIR.
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path(FILE_STORAGE_DIR)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, agent_id: str) -> Path:
        """Возвращает путь к файлу истории для данного агента."""
        return self.storage_dir / f"{agent_id}.pkl"

    def save_history(self, agent_id: str, history: list[Prompt]) -> None:
        """
        Сохраняет историю сообщений в файл.

        Args:
            agent_id: UUID агента.
            history: Список объектов Prompt для сохранения.
        """
        file_path = self._get_file_path(agent_id)
        with open(file_path, "wb") as f:
            pickle.dump(history, f)

    def load_history(self, agent_id: str) -> list[Prompt]:
        """
        Загружает историю сообщений из файла.

        Args:
            agent_id: UUID агента.

        Returns:
            Список объектов Prompt. Пустой список, если файл не найден.
        """
        file_path = self._get_file_path(agent_id)
        if not file_path.exists():
            return []

        with open(file_path, "rb") as f:
            return pickle.load(f)

    def delete_history(self, agent_id: str) -> None:
        """
        Удаляет файл истории для данного агента.

        Args:
            agent_id: UUID агента.
        """
        file_path = self._get_file_path(agent_id)
        if file_path.exists():
            file_path.unlink()

    def history_exists(self, agent_id: str) -> bool:
        """
        Проверяет, существует ли файл истории для данного агента.

        Args:
            agent_id: UUID агента.

        Returns:
            True, если файл существует, иначе False.
        """
        return self._get_file_path(agent_id).exists()
