from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.infrastructure.persistence.orm.base import Base

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.agent_knowledge_base_orm import (
        AgentKnowledgeBaseORM,
    )
    from core.infrastructure.persistence.orm.document_orm import DocumentORM


class KnowledgeBaseORM(Base):
    """ORM модель базы знаний (RAG).

    Векторы чанков хранятся не здесь, а в отдельной виртуальной таблице
    sqlite-vec с именем ``vector_table`` (например, ``vec_chunks_kb_1``).
    Векторные таблицы не описываются в ``Base.metadata``.
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_table: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now().astimezone()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    documents: Mapped[list[DocumentORM]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    agent_links: Mapped[list[AgentKnowledgeBaseORM]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseORM(id={self.id}, name={self.name})>"
