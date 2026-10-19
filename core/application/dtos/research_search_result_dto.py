from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ResearchSearchResultDTO:
    """Результат поиска статей во внешнем источнике."""

    library: ResearchLibraryDTO
    query: str
    total: int
    articles: list[ArticleCandidateDTO] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
