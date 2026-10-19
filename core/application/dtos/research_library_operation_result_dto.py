from __future__ import annotations

from dataclasses import dataclass

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ResearchLibraryOperationResultDTO:
    """Результат открепления/удаления научной библиотеки."""

    success: bool
    message: str
    library: ResearchLibraryDTO | None = None
    affected_chats: int = 0
    deleted_articles: int = 0
    deleted_documents: int = 0
