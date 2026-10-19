from __future__ import annotations

from core.application.dtos.research_article_dto import ResearchArticleDTO
from core.application.mappers.research_mapper import research_article_to_dto
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class ListResearchArticlesUseCase:
    """Список статей активной библиотеки чата."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository

    def execute(
        self,
        agent_id: int,
        *,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        library_name: str | None = None,
    ) -> list[ResearchArticleDTO]:
        library = self._ensure_library.execute(agent_id, library_name)
        articles = self._articles.list(
            library.id,
            query=query,
            year_from=year_from,
            year_to=year_to,
            status=status,
            limit=limit,
            offset=offset,
        )
        return [research_article_to_dto(article) for article in articles]
