from __future__ import annotations

from core.application.dtos.research_review_context_dto import (
    ResearchReviewContextDTO,
    ReviewContextArticleDTO,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)
from core.domain.entities.research_article import ResearchArticle


class BuildReviewContextUseCase:
    """Собирает компактный контекст библиотеки для систематического обзора."""

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
        topic: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        max_chars: int = 60000,
        limit: int = 40,
        offset: int = 0,
        library_name: str | None = None,
    ) -> ResearchReviewContextDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_topic = (topic or "").strip() or None
        matched = self._articles.list(
            library.id,
            query=clean_topic,
            year_from=year_from,
            year_to=year_to,
            limit=5000,
        )
        selected = matched[offset : offset + max(1, min(limit, 100))]

        articles: list[ReviewContextArticleDTO] = []
        used_chars = 0
        truncated = len(matched) > offset + len(selected)
        for article in selected:
            content = (article.summary or article.abstract or "").strip()
            if not content:
                content = "Сводка и аннотация отсутствуют."
            remaining = max_chars - used_chars
            if remaining <= 200:
                truncated = True
                break
            if len(content) > remaining:
                content = content[:remaining].rstrip() + "…"
                truncated = True
            articles.append(self._to_dto(article, content))
            used_chars += len(content)

        return ResearchReviewContextDTO(
            library=library,
            topic=clean_topic,
            total_matched=len(matched),
            returned=len(articles),
            truncated=truncated,
            articles=articles,
        )

    @staticmethod
    def _to_dto(
        article: ResearchArticle, content: str
    ) -> ReviewContextArticleDTO:
        authors = list(article.authors)
        if len(authors) > 3:
            author_key = authors[0] + " et al."
        elif authors:
            author_key = ", ".join(authors)
        else:
            author_key = "Без автора"
        year = article.publication_year or "б.г."
        citation = f"{author_key} ({year}). {article.title}"
        return ReviewContextArticleDTO(
            article_id=article.id or 0,
            citation=citation,
            title=article.title,
            authors=authors,
            publication_year=article.publication_year,
            venue=article.venue,
            doi=article.doi,
            status=article.status,
            has_summary=bool(article.summary),
            content=content,
        )
