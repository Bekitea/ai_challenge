from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)


class ListResearchLibrariesUseCase:
    """Список всех научных библиотек со статистикой статей."""

    def __init__(self, library_repository: ResearchLibraryRepository):
        self._libraries = library_repository

    def execute(self) -> list[ResearchLibraryDTO]:
        result: list[ResearchLibraryDTO] = []
        for library in self._libraries.list():
            dto = research_library_to_dto(library)
            dto.article_count = (
                self._libraries.count_articles(library.id)
                if library.id is not None
                else 0
            )
            result.append(dto)
        return result
