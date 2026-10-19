from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_article_dto import ResearchArticleDTO
from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ResearchArticleListDTO:
    """Страница статей научной библиотеки с общим числом записей."""

    library: ResearchLibraryDTO
    total: int
    limit: int
    offset: int
    articles: list[ResearchArticleDTO] = field(default_factory=list)
