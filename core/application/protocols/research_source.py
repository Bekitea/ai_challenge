from __future__ import annotations

from typing import Protocol

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO


class ResearchSource(Protocol):
    """Внешний источник научных статей (поиск и метаданные)."""

    def search(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 20,
        sort: str = "relevance",
        language: str | None = None,
        oa_only: bool = True,
    ) -> list[ArticleCandidateDTO]: ...

    def get_by_identifier(
        self, identifier: str
    ) -> ArticleCandidateDTO | None: ...
