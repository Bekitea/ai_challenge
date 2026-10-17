from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.infrastructure.persistence.orm.base import Base

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.agent_orm import AgentORM
    from core.infrastructure.persistence.orm.knowledge_base_orm import KnowledgeBaseORM


class AgentKnowledgeBaseORM(Base):
    """Таблица связи агента и подключённой к нему базы знаний (RAG)."""

    __tablename__ = "agent_knowledge_bases"
    __table_args__ = (
        UniqueConstraint("agent_id", "knowledge_base_id", name="uq_agent_knowledge_base"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now().astimezone()
    )

    agent: Mapped[AgentORM] = relationship(back_populates="knowledge_base_links")
    knowledge_base: Mapped[KnowledgeBaseORM] = relationship(
        back_populates="agent_links"
    )

    def __repr__(self) -> str:
        return (
            f"<AgentKnowledgeBaseORM(agent_id={self.agent_id}, "
            f"knowledge_base_id={self.knowledge_base_id})>"
        )
