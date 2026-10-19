from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ResearchArticleDTO:
    """Статья библиотеки для presentation/MCP."""

    id: int
    library_id: int
    title: str
    openalex_id: str | None = None
    doi: str | None = None
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    venue: str | None = None
    language: str | None = None
    abstract: str | None = None
    cited_by_count: int | None = None
    is_open_access: bool = False
    pdf_url: str | None = None
    landing_url: str | None = None
    source: str | None = None
    status: str = "candidate"
    error_message: str | None = None
    document_id: int | None = None
    summary: str | None = None
    summary_model: str | None = None
    summary_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    in_library: bool = True
