from __future__ import annotations

from core.application.dtos.research_search_result_dto import (
    ResearchSearchResultDTO,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.protocols.research_source import ResearchSource
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class SearchResearchArticlesUseCase:
    """Ищет статьи во внешнем источнике в контексте активной библиотеки чата."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
        source: ResearchSource,
        default_limit: int,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository
        self._source = source
        self._default_limit = max(1, default_limit)

    def execute(
        self,
        agent_id: int,
        query: str,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int | None = None,
        sort: str = "relevance",
        language: str | None = None,
        oa_only: bool = True,
        library_name: str | None = None,
    ) -> ResearchSearchResultDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_query = (query or "").strip()
        if not clean_query:
            raise ValueError("Поисковый запрос не может быть пустым.")

        effective_year_from = (
            year_from if year_from is not None else library.year_from
        )
        effective_year_to = year_to if year_to is not None else library.year_to
        effective_language = language if language is not None else library.language
        effective_limit = max(1, min(limit or self._default_limit, 50))

        articles = self._source.search(
            clean_query,
            year_from=effective_year_from,
            year_to=effective_year_to,
            limit=effective_limit,
            sort=sort,
            language=effective_language,
            oa_only=oa_only,
        )
        for candidate in articles:
            identifier = candidate.doi or candidate.openalex_id
            if not identifier:
                continue
            existing = self._articles.get_by_identifier(library.id, identifier)
            if existing is not None:
                candidate.in_library = True
                candidate.library_status = existing.status

        return ResearchSearchResultDTO(
            library=library,
            query=clean_query,
            total=len(articles),
            articles=articles,
            year_from=effective_year_from,
            year_to=effective_year_to,
        )
