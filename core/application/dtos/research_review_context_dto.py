from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ReviewContextArticleDTO:
    """Компактная карточка статьи для систематического обзора/гипотез."""

    article_id: int
    citation: str
    title: str
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    venue: str | None = None
    doi: str | None = None
    status: str = "indexed"
    has_summary: bool = False
    content: str = ""


@dataclass
class ResearchReviewContextDTO:
    """Контекст библиотеки для синтеза обзора или гипотез агентом."""

    library: ResearchLibraryDTO
    topic: str | None
    total_matched: int
    returned: int
    truncated: bool
    articles: list[ReviewContextArticleDTO] = field(default_factory=list)


@dataclass
class ResearchHypothesisContextDTO:
    """Контекст для генерации гипотез: профиль, статьи и RAG-фрагменты."""

    library: ResearchLibraryDTO
    goal: str | None
    articles: list[ReviewContextArticleDTO] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)
    truncated: bool = False
