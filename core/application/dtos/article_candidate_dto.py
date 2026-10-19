from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArticleCandidateDTO:
    """Метаданные статьи, найденной во внешнем источнике."""

    title: str
    openalex_id: str | None = None
    doi: str | None = None
    authors: list[str] | None = None
    publication_year: int | None = None
    venue: str | None = None
    language: str | None = None
    abstract: str | None = None
    cited_by_count: int | None = None
    is_open_access: bool = False
    pdf_url: str | None = None
    landing_url: str | None = None
    source: str | None = "openalex"
    in_library: bool = False
    library_status: str | None = None
