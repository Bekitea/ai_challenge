from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.infrastructure.persistence.orm.base import Base

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.research_library_orm import (
        ResearchLibraryORM,
    )


class ResearchArticleORM(Base):
    """ORM статьи научной библиотеки."""

    __tablename__ = "research_articles"
    __table_args__ = (
        UniqueConstraint(
            "library_id", "doi", name="uq_research_article_library_doi"
        ),
        UniqueConstraint(
            "library_id",
            "openalex_id",
            name="uq_research_article_library_openalex",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    library_id: Mapped[int] = mapped_column(
        ForeignKey("research_libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    openalex_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    venue: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_by_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_open_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="candidate", index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now().astimezone()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    library: Mapped[ResearchLibraryORM] = relationship(back_populates="articles")

    def __repr__(self) -> str:
        return (
            f"<ResearchArticleORM(id={self.id}, library_id={self.library_id}, "
            f"status={self.status}, title={self.title[:40]!r})>"
        )
