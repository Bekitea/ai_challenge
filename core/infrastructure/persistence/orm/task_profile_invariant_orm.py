from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.infrastructure.persistence.orm.base import Base

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.task_profile_orm import TaskProfileORM


class TaskProfileInvariantORM(Base):
    """
    ORM модель для хранения инвариантов профиля задачи.
    Инварианты — это строгие правила/ограничения, которые должны соблюдаться
    в диалоге (например, стек технологий, архитектурные решения, бизнес-правила).

    Атрибуты:
    id: Числовой ID инварианта (primary key).
    profile_id: UUID профиля задачи (foreign key).
    text: Текст инварианта.
    created_at: Дата создания инварианта.
    """

    __tablename__ = "task_profile_invariants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("task_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now().astimezone(),
    )

    # Relationship back to TaskProfile
    profile: Mapped[TaskProfileORM] = relationship(back_populates="invariants")

    def __repr__(self) -> str:
        return f"<TaskProfileInvariantORM(id={self.id}, profile_id={self.profile_id})>"
