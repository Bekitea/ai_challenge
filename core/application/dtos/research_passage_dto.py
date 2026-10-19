from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ResearchPassageDTO:
    """Фрагмент статьи, найденный RAG-поиском в научной библиотеке."""

    article_id: int | None
    document_id: int
    title: str
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    chunk_index: int = 0
    text: str = ""
    relevance: float | None = None


@dataclass
class ResearchLibraryHitsDTO:
    """Результат RAG-поиска по активной научной библиотеке."""

    library: ResearchLibraryDTO
    query: str
    has_knowledge_base: bool
    hits: list[ResearchPassageDTO] = field(default_factory=list)
