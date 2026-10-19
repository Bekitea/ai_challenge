from __future__ import annotations

from core.application.dtos.research_recommendation_dto import (
    RecommendedArticleDTO,
    ResearchRecommendationsDTO,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.services.rag_service import RagService
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class RecommendResearchArticlesUseCase:
    """Ранжирует статьи библиотеки под конкретный вопрос (для чтения)."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
        rag_service: RagService,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository
        self._rag = rag_service

    def execute(
        self,
        agent_id: int,
        question: str,
        *,
        top_k: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
        library_name: str | None = None,
    ) -> ResearchRecommendationsDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_question = (question or "").strip()
        if not clean_question:
            raise ValueError("Вопрос для рекомендаций не может быть пустым.")
        if library.knowledge_base_id is None:
            return ResearchRecommendationsDTO(
                library=library,
                question=clean_question,
                has_knowledge_base=False,
            )

        result = self._rag.retrieve_from_knowledge_base(
            library.knowledge_base_id,
            clean_question,
            top_k=max(1, min(top_k * 3, 60)),
        )

        grouped: dict[int, RecommendedArticleDTO] = {}
        for chunk in result.chunks:
            article = self._articles.get_by_document(
                library.id, chunk.document_id
            )
            if article is None or article.id is None:
                continue
            if year_from is not None and (
                article.publication_year is None
                or article.publication_year < year_from
            ):
                continue
            if year_to is not None and (
                article.publication_year is None
                or article.publication_year > year_to
            ):
                continue

            relevance = chunk.relevance or 0.0
            existing = grouped.get(article.id)
            if existing is None:
                grouped[article.id] = RecommendedArticleDTO(
                    article_id=article.id,
                    title=article.title,
                    authors=list(article.authors),
                    publication_year=article.publication_year,
                    doi=article.doi,
                    status=article.status,
                    score=relevance,
                    summary=article.summary,
                    snippets=[chunk.text],
                )
            else:
                existing.score = max(existing.score or 0.0, relevance)
                if len(existing.snippets) < 3 and chunk.text not in existing.snippets:
                    existing.snippets.append(chunk.text)

        ranked = sorted(
            grouped.values(),
            key=lambda item: (
                item.score or 0.0,
                item.publication_year or 0,
            ),
            reverse=True,
        )[: max(1, min(top_k, 30))]

        return ResearchRecommendationsDTO(
            library=library,
            question=clean_question,
            has_knowledge_base=result.has_knowledge_bases,
            articles=ranked,
        )
