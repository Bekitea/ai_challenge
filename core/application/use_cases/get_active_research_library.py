from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)


class GetActiveResearchLibraryUseCase:
    """Возвращает активную библиотеку чата без автосоздания."""

    def __init__(self, library_repository: ResearchLibraryRepository):
        self._libraries = library_repository

    def execute(self, agent_id: int) -> ResearchLibraryDTO | None:
        library = self._libraries.get_bound_library(agent_id)
        if library is None or library.id is None:
            return None
        dto = research_library_to_dto(library)
        dto.article_count = self._libraries.count_articles(library.id)
        return dto
