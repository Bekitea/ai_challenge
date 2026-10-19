from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from core.infrastructure.persistence.orm.base import Base


class AgentResearchLibraryORM(Base):
    """Активная научная библиотека чата (одна на чат)."""

    __tablename__ = "agent_research_libraries"

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    library_id: Mapped[int] = mapped_column(
        ForeignKey("research_libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now().astimezone()
    )

    def __repr__(self) -> str:
        return (
            f"<AgentResearchLibraryORM(agent_id={self.agent_id}, "
            f"library_id={self.library_id})>"
        )
