import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TaskProfile:
    """Профиль задачи с памятью о фактах задачи."""
    id: str
    name: str
    description: str
    created_at: datetime
    facts: list[str] = field(default_factory=list)


class TaskProfileRepository(ABC):
    """Абстракция для хранения и управления профилями задач."""

    @abstractmethod
    def get_all_profiles(self) -> list[TaskProfile]:
        """
        Получает все профили задач.

        Returns:
            Список всех профилей задач.
        """

    @abstractmethod
    def get_profile_by_id(self, profile_id: str) -> TaskProfile | None:
        """
        Получает профиль задачи по UUID.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            TaskProfile или None, если профиль не найден.
        """

    @abstractmethod
    def create_profile(self, name: str, description: str, preferences: str = "") -> TaskProfile:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.
            preferences: Инструкции и предпочтения пользователя (опционально).

        Returns:
            TaskProfile: Созданный профиль задачи.
        """

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        """
        Удаляет профиль задачи.

        Args:
            profile_id: UUID профиля для удаления.

        Returns:
            True, если профиль был удалён, False если не найден.
        """

    @abstractmethod
    def save_facts(self, profile_id: str, facts: list[str]) -> None:
        """
        Сохраняет факты в профиль задачи.

        Args:
            profile_id: UUID профиля задачи.
            facts: Список фактов для сохранения.
        """

    @abstractmethod
    def is_profile_linked_to_agents(self, profile_id: str) -> bool:
        """
        Проверяет, привязан ли профиль к каким-либо агентам.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            True, если профиль привязан к агентам, False иначе.
        """


class DatabaseTaskProfileRepository(TaskProfileRepository):
    """
    Реализация TaskProfileRepository с хранением метаданных в БД и фактов в файлах.

    Метаданные (id, name, description, created_at) хранятся в таблице task_profiles.
    Факты хранятся в отдельных файлах {profile_id}.pkl в директории profiles_dir.
    """

    def __init__(self, profiles_dir: str, session_factory):
        """
        Инициализирует репозиторий.

        Args:
            profiles_dir: Путь к директории хранения фактов профилей задач.
            session_factory: Фабрика сессий БД для работы с метаданными.
        """
        from storage.orm_models import TaskProfileORM

        self._profiles_dir = Path(profiles_dir)
        self._session_factory = session_factory
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._orm_class = TaskProfileORM

    def _get_facts_path(self, profile_id: str) -> Path:
        """Возвращает путь к файлу фактов профиля."""
        return self._profiles_dir / f"{profile_id}.pkl"

    def _load_facts(self, profile_id: str) -> list[str]:
        """Загружает факты из файла."""
        facts_path = self._get_facts_path(profile_id)
        if not facts_path.exists():
            return []

        try:
            with open(facts_path, "rb") as f:
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError, AttributeError):
            return []

    def _save_facts_to_file(self, profile_id: str, facts: list[str]) -> None:
        """Сохраняет факты в файл."""
        facts_path = self._get_facts_path(profile_id)
        with open(facts_path, "wb") as f:
            pickle.dump(facts, f)

    def _get_session(self):
        """Возвращает новую сессию БД."""
        return self._session_factory()

    def get_all_profiles(self) -> list[TaskProfile]:
        """Загружает все профили задач из БД с фактами из файлов."""
        from sqlalchemy import select

        with self._get_session() as session:
            stmt = select(self._orm_class).order_by(self._orm_class.created_at.desc())
            orm_profiles = session.execute(stmt).scalars().all()

        profiles = []
        for orm in orm_profiles:
            facts = self._load_facts(orm.id)
            profiles.append(TaskProfile(
                id=orm.id,
                name=orm.name,
                description=orm.description,
                created_at=orm.created_at,
                facts=facts,
                preferences=orm.preferences or ""
            ))

        return profiles

    def get_profile_by_id(self, profile_id: str) -> TaskProfile | None:
        """Загружает профиль задачи по UUID из БД с фактами из файла."""
        from sqlalchemy import select

        with self._get_session() as session:
            stmt = select(self._orm_class).where(self._orm_class.id == profile_id)
            orm = session.execute(stmt).scalars().first()

        if orm is None:
            return None

        facts = self._load_facts(profile_id)
        return TaskProfile(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            created_at=orm.created_at,
            facts=facts,
            preferences=orm.preferences or ""
        )

    def create_profile(self, name: str, description: str, preferences: str = "") -> TaskProfile:
        """Создаёт новый профиль задачи в БД и пустой файл фактов."""
        from uuid import uuid4


        profile_id = str(uuid4())
        created_at = datetime.now().astimezone()

        # Создаём запись в БД
        orm_profile = self._orm_class(
            id=profile_id,
            name=name,
            description=description,
            created_at=created_at,
            preferences=preferences or ""
        )

        with self._get_session() as session:
            session.add(orm_profile)
            session.commit()

        # Создаём пустой файл для фактов
        self._save_facts_to_file(profile_id, [])

        return TaskProfile(
            id=profile_id,
            name=name,
            description=description,
            created_at=created_at,
            facts=[],
            preferences=preferences or ""
        )

    def delete_profile(self, profile_id: str) -> bool:
        """Удаляет профиль из БД и файл фактов."""
        from sqlalchemy import delete, select

        with self._get_session() as session:
            stmt = select(self._orm_class).where(self._orm_class.id == profile_id)
            orm = session.execute(stmt).scalars().first()

            if orm is None:
                return False

            # Удаляем из БД
            delete_stmt = delete(self._orm_class).where(self._orm_class.id == profile_id)
            session.execute(delete_stmt)
            session.commit()

        # Удаляем файл фактов
        facts_path = self._get_facts_path(profile_id)
        if facts_path.exists():
            facts_path.unlink()

        return True

    def save_facts(self, profile_id: str, facts: list[str]) -> None:
        """Сохраняет факты в файл профиля задачи."""
        # Проверяем существование профиля в БД
        profile = self.get_profile_by_id(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")

        # Сохраняем только факты в файл
        self._save_facts_to_file(profile_id, facts)

    def is_profile_linked_to_agents(self, profile_id: str) -> bool:
        """Проверяет, привязан ли профиль к каким-либо агентам через БД."""
        from sqlalchemy import select

        from storage.orm_models import AgentORM

        with self._get_session() as session:
            stmt = select(AgentORM).where(AgentORM.task_profile_id == profile_id)
            result = session.execute(stmt).scalars().first()
            return result is not None
