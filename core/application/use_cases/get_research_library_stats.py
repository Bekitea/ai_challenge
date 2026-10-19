from __future__ import annotations

from collections import Counter

from core.application.dtos.research_library_stats_dto import (
    ResearchLibraryStatsDTO,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class GetResearchLibraryStatsUseCase:
    """Считает статистику активной научной библиотеки чата."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository

    def execute(
        self, agent_id: int, *, library_name: str | None = None
    ) -> ResearchLibraryStatsDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        articles = self._articles.list(library.id, limit=5000, offset=0)
        statuses = Counter(article.status for article in articles)
        years = Counter(
            article.publication_year
            for article in articles
            if article.publication_year is not None
        )
        with_summary = sum(1 for article in articles if article.summary)
        return ResearchLibraryStatsDTO(
            library_id=library.id,
            library_name=library.name,
            total=len(articles),
            by_status=dict(statuses),
            by_year=dict(sorted(years.items())),
            with_summary=with_summary,
            missing_summary=len(articles) - with_summary,
            indexed_fulltext=statuses.get("indexed", 0),
            abstract_only=statuses.get("abstract_only", 0),
            errors=statuses.get("error", 0),
        )
