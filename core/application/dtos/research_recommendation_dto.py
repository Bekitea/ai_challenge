from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class RecommendedArticleDTO:
    """Статья, рекомендованная для чтения по конкретному вопросу."""

    article_id: int
    title: str
    authors: list[str] = field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    status: str = "indexed"
    score: float | None = None
    summary: str | None = None
    snippets: list[str] = field(default_factory=list)


@dataclass
class ResearchRecommendationsDTO:
    """Ранжированные статьи активной библиотеки по вопросу пользователя."""

    library: ResearchLibraryDTO
    question: str
    has_knowledge_base: bool
    articles: list[RecommendedArticleDTO] = field(default_factory=list)
