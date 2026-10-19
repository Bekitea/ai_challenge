from __future__ import annotations

from core.application.dtos.research_passage_dto import (
    ResearchLibraryHitsDTO,
    ResearchPassageDTO,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.services.rag_service import RagService
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)


class SearchResearchLibraryUseCase:
    """RAG-поиск по базе знаний активной научной библиотеки чата."""

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
        query: str,
        *,
        top_k: int = 8,
        year_from: int | None = None,
        year_to: int | None = None,
        library_name: str | None = None,
        reranker_enabled: bool | None = None,
    ) -> ResearchLibraryHitsDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_query = (query or "").strip()
        if not clean_query:
            raise ValueError("Поисковый запрос не может быть пустым.")
        if library.knowledge_base_id is None:
            return ResearchLibraryHitsDTO(
                library=library,
                query=clean_query,
                has_knowledge_base=False,
            )

        result = self._rag.retrieve_from_knowledge_base(
            library.knowledge_base_id,
            clean_query,
            top_k=max(1, min(top_k, 30)),
            reranker_enabled=reranker_enabled,
        )

        hits: list[ResearchPassageDTO] = []
        for chunk in result.chunks:
            article = self._articles.get_by_document(
                library.id, chunk.document_id
            )
            if article is not None:
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
                hits.append(
                    ResearchPassageDTO(
                        article_id=article.id,
                        document_id=chunk.document_id,
                        title=article.title,
                        authors=list(article.authors),
                        publication_year=article.publication_year,
                        doi=article.doi,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        relevance=chunk.relevance,
                    )
                )
            else:
                hits.append(
                    ResearchPassageDTO(
                        article_id=None,
                        document_id=chunk.document_id,
                        title=chunk.document_name,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        relevance=chunk.relevance,
                    )
                )

        return ResearchLibraryHitsDTO(
            library=library,
            query=clean_query,
            has_knowledge_base=result.has_knowledge_bases,
            hits=hits,
        )
