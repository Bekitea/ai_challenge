from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)


class UpdateResearchLibraryProfileUseCase:
    """Обновляет имя и профиль активной научной библиотеки чата."""

    def __init__(self, library_repository: ResearchLibraryRepository):
        self._libraries = library_repository

    def execute(
        self,
        agent_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        goal: str | None = None,
        field: str | None = None,
        keywords: list[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        language: str | None = None,
    ) -> ResearchLibraryDTO:
        library = self._libraries.get_bound_library(agent_id)
        if library is None or library.id is None:
            raise ValueError(
                "У чата ещё нет активной научной библиотеки. "
                "Сначала выполните поиск или создайте библиотеку."
            )

        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Имя научной библиотеки не может быть пустым.")
            existing = self._libraries.get_by_name(clean_name)
            if existing is not None and existing.id != library.id:
                raise ValueError(f"Научная библиотека '{clean_name}' уже существует.")
            library.name = clean_name
        if description is not None:
            library.description = description.strip() or None
        if goal is not None:
            library.goal = goal.strip() or None
        if field is not None:
            library.field = field.strip() or None
        if keywords is not None:
            library.keywords = [item.strip() for item in keywords if item.strip()]
        if year_from is not None:
            library.year_from = year_from
        if year_to is not None:
            library.year_to = year_to
        if language is not None:
            library.language = language.strip() or None

        updated = self._libraries.update(library)
        dto = research_library_to_dto(updated)
        dto.article_count = (
            self._libraries.count_articles(updated.id)
            if updated.id is not None
            else 0
        )
        return dto
