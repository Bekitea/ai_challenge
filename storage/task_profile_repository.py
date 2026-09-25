import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agents import TaskProfile
from storage.orm_models import TaskProfileInvariantORM


@dataclass
class TaskProfile:
    """Профиль задачи с памятью о фактах задачи."""
    id: str
    name: str
    description: str
    created_at: datetime
    facts: list[str] = field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = field(default_factory=list)


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
    def create_profile(self, name: str, description: str, preferences: str = "", nvariants: list[str] | None = None) -> TaskProfile:
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

    @abstractmethod
    def add_invariant(self, profile_id: str, text: str) -> int:
        """Добавляет инвариант в профиль. Возвращает ID нового инварианта."""
    
    @abstractmethod
    def remove_invariant(self, invariant_id: int) -> bool:
        """Удаляет инвариант по ID. Возвращает True если удалён."""
    
    @abstractmethod
    def get_invariants(self, profile_id: str) -> list[dict]:
        """Возвращает список инвариантов профиля."""


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

    def _orm_to_task_profile(self, orm) -> TaskProfile:
        """Преобразует ORM объект в TaskProfile, загружая факты и инварианты."""
        facts = self._load_facts(orm.id)
        invariants = [inv.text for inv in orm.invariants]
        return TaskProfile(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            created_at=orm.created_at,
            facts=facts,
            preferences=orm.preferences or "",
            invariants=invariants,
        )
    
    def get_all_profiles(self) -> list[TaskProfile]:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        with self._get_session() as session:
            stmt = (
                select(self._orm_class)
                .options(selectinload(self._orm_class.invariants))
                .order_by(self._orm_class.created_at.desc())
            )
            orm_profiles = session.execute(stmt).scalars().all()
            return [self._orm_to_task_profile(orm) for orm in orm_profiles]
    
    def get_profile_by_id(self, profile_id: str) -> TaskProfile | None:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        with self._get_session() as session:
            stmt = (
                select(self._orm_class)
                .options(selectinload(self._orm_class.invariants))
                .where(self._orm_class.id == profile_id)
            )
            orm = session.execute(stmt).scalars().first()
            if orm is None:
                return None
            return self._orm_to_task_profile(orm)
    
    def create_profile(
        self,
        name: str,
        description: str,
        preferences: str = "",
        invariants: list[str] | None = None,
    ) -> TaskProfile:
        from uuid import uuid4
        profile_id = str(uuid4())
        created_at = datetime.now().astimezone()
        
        orm_profile = self._orm_class(
            id=profile_id,
            name=name,
            description=description,
            created_at=created_at,
            preferences=preferences or "",
        )
        
        with self._get_session() as session:
            session.add(orm_profile)
            session.flush()
            
            if invariants:
                for inv_text in invariants:
                    stripped = inv_text.strip()
                    if stripped:
                        inv_orm = TaskProfileInvariantORM(
                            profile_id=profile_id,
                            text=stripped,
                        )
                        session.add(inv_orm)
            
            session.commit()
            session.refresh(orm_profile)
            
            return self._orm_to_task_profile(orm_profile)
    
    def delete_profile(self, profile_id: str) -> bool:
        from sqlalchemy import delete, select
        with self._get_session() as session:
            stmt = select(self._orm_class).where(self._orm_class.id == profile_id)
            orm = session.execute(stmt).scalars().first()
            if orm is None:
                return False
            delete_stmt = delete(self._orm_class).where(self._orm_class.id == profile_id)
            session.execute(delete_stmt)
            session.commit()
            facts_path = self._get_facts_path(profile_id)
            if facts_path.exists():
                facts_path.unlink()
            return True
    
    def save_facts(self, profile_id: str, facts: list[str]) -> None:
        profile = self.get_profile_by_id(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        self._save_facts_to_file(profile_id, facts)
    
    def is_profile_linked_to_agents(self, profile_id: str) -> bool:
        from sqlalchemy import select
        from storage.orm_models import AgentORM
        with self._get_session() as session:
            stmt = select(AgentORM).where(AgentORM.task_profile_id == profile_id)
            result = session.execute(stmt).scalars().first()
            return result is not None
    
    def add_invariant(self, profile_id: str, text: str) -> int:
        """Добавляет инвариант в профиль. Возвращает ID нового инварианта."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        with self._get_session() as session:
            stmt = (
                select(self._orm_class)
                .options(selectinload(self._orm_class.invariants))
                .where(self._orm_class.id == profile_id)
            )
            orm = session.execute(stmt).scalars().first()
            if orm is None:
                raise ValueError(f"Profile {profile_id} not found")
            
            inv_orm = TaskProfileInvariantORM(
                profile_id=profile_id,
                text=text.strip(),
            )
            session.add(inv_orm)
            session.commit()
            session.refresh(inv_orm)
            return inv_orm.id
    
    def remove_invariant(self, invariant_id: int) -> bool:
        """Удаляет инвариант по ID."""
        from sqlalchemy import select
        with self._get_session() as session:
            stmt = select(TaskProfileInvariantORM).where(
                TaskProfileInvariantORM.id == invariant_id
            )
            inv_orm = session.execute(stmt).scalars().first()
            if inv_orm is None:
                return False
            session.delete(inv_orm)
            session.commit()
            return True
    
    def get_invariants(self, profile_id: str) -> list[dict]:
        """Возвращает список инвариантов профиля как словари {id, text, created_at}."""
        from sqlalchemy import select
        with self._get_session() as session:
            stmt = (
                select(TaskProfileInvariantORM)
                .where(TaskProfileInvariantORM.profile_id == profile_id)
                .order_by(TaskProfileInvariantORM.created_at)
            )
            inv_orms = session.execute(stmt).scalars().all()
            return [
                {
                    "id": inv.id,
                    "text": inv.text,
                    "created_at": inv.created_at,
                }
                for inv in inv_orms
            ]
    def is_profile_linked_to_agents(self, profile_id: str) -> bool:
        """Проверяет, привязан ли профиль к каким-либо агентам через БД."""
        from sqlalchemy import select

        from storage.orm_models import AgentORM

        with self._get_session() as session:
            stmt = select(AgentORM).where(AgentORM.task_profile_id == profile_id)
            result = session.execute(stmt).scalars().first()
            return result is not None
