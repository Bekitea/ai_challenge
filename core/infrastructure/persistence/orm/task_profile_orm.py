from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.infrastructure.persistence.orm.base import Base

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.agent_orm import AgentORM
    from core.infrastructure.persistence.orm.task_profile_invariant_orm import (
        TaskProfileInvariantORM,
    )


class TaskProfileORM(Base):
    """
    ORM модель для хранения метаданных профиля задачи.

    Атрибуты:
        id: UUID профиля (primary key).
        name: Название профиля задачи.
        description: Описание задачи.
        created_at: Дата создания профиля.
        preferences: Инструкции и предпочтения пользователя (текст).
        agents: Связь с агентами (many-to-one).

    Примечание: Факты задачи хранятся в файловом хранилище через TaskProfileRepository,
    а не в БД. Эта модель содержит только метаданные для отображения в списке профилей.
    """

    __tablename__ = "task_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now().astimezone()
    )
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True, default="")

    # Связь с агентами
    agents: Mapped[list[AgentORM]] = relationship(
        back_populates="task_profile", foreign_keys="AgentORM.task_profile_id"
    )

    invariants: Mapped[list[TaskProfileInvariantORM]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TaskProfileORM(id={self.id}, name={self.name})>"
