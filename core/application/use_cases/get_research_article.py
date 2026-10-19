from __future__ import annotations

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.dtos.research_article_dto import ResearchArticleDTO
from core.application.mappers.research_mapper import research_article_to_dto
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.protocols.research_source import ResearchSource
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class GetResearchArticleUseCase:
    """Возвращает статью из библиотеки или её метаданные из внешнего источника."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
        source: ResearchSource,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository
        self._source = source

    def execute(
        self,
        agent_id: int,
        identifier: str,
        *,
        library_name: str | None = None,
    ) -> ResearchArticleDTO | ArticleCandidateDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_identifier = (identifier or "").strip()
        if not clean_identifier:
            raise ValueError("Не указан DOI или OpenAlex ID.")

        article = self._articles.get_by_identifier(library.id, clean_identifier)
        if article is not None:
            return research_article_to_dto(article)

        candidate = self._source.get_by_identifier(clean_identifier)
        if candidate is None:
            raise ValueError(
                f"Статья '{clean_identifier}' не найдена ни в библиотеке, "
                "ни в OpenAlex."
            )
        candidate.in_library = False
        return candidate
