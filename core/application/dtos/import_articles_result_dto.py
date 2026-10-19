from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ImportedArticleResultDTO:
    """Результат импорта одной статьи."""

    identifier: str
    ok: bool
    status: str
    article_id: int | None = None
    document_id: int | None = None
    title: str | None = None
    detail: str | None = None


@dataclass
class ImportArticlesResultDTO:
    """Результат пакетного импорта статей в библиотеку."""

    library: ResearchLibraryDTO
    results: list[ImportedArticleResultDTO] = field(default_factory=list)
