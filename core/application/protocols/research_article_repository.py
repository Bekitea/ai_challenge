from __future__ import annotations

from typing import Protocol

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.domain.entities.research_article import ResearchArticle


class ResearchArticleRepository(Protocol):
    """Репозиторий статей научной библиотеки (строго в рамках library_id)."""

    def upsert(
        self,
        library_id: int,
        candidate: ArticleCandidateDTO,
        status: str,
    ) -> ResearchArticle: ...

    def get(self, article_id: int) -> ResearchArticle | None: ...

    def get_by_identifier(
        self, library_id: int, identifier: str
    ) -> ResearchArticle | None: ...

    def get_by_document(
        self, library_id: int, document_id: int
    ) -> ResearchArticle | None: ...

    def list(
        self,
        library_id: int,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchArticle]: ...

    def update(self, article: ResearchArticle) -> ResearchArticle: ...

    def set_status(
        self,
        article_id: int,
        status: str,
        error_message: str | None = None,
        document_id: int | None = None,
    ) -> ResearchArticle | None: ...

    def set_summary(
        self,
        article_id: int,
        summary: str,
        model: str | None,
    ) -> ResearchArticle | None: ...

    def delete(self, article_id: int) -> bool: ...

    def count(
        self,
        library_id: int,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
    ) -> int: ...
