from __future__ import annotations

from core.application.dtos.research_article_list_dto import (
    ResearchArticleListDTO,
)
from core.application.mappers.research_mapper import (
    research_article_to_dto,
    research_library_to_dto,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)


class ListResearchLibraryArticlesUseCase:
    """Список статей конкретной научной библиотеки с фильтрами и итогом."""

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        article_repository: ResearchArticleRepository,
    ):
        self._libraries = library_repository
        self._articles = article_repository

    def execute(
        self,
        library_id: int,
        *,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ResearchArticleListDTO:
        library = self._libraries.get(library_id)
        if library is None or library.id is None:
            raise ValueError(f"Научная библиотека #{library_id} не найдена.")

        effective_limit = max(1, min(limit, 500))
        articles = self._articles.list(
            library_id,
            query=query,
            year_from=year_from,
            year_to=year_to,
            status=status,
            limit=effective_limit,
            offset=offset,
        )
        total = self._articles.count(
            library_id,
            query=query,
            year_from=year_from,
            year_to=year_to,
            status=status,
        )
        library_dto = research_library_to_dto(library)
        library_dto.article_count = self._libraries.count_articles(library_id)
        return ResearchArticleListDTO(
            library=library_dto,
            total=total,
            limit=effective_limit,
            offset=max(0, offset),
            articles=[
                research_article_to_dto(article) for article in articles
            ],
        )
