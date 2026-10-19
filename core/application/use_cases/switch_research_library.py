from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.bind_research_library import (
    BindResearchLibraryUseCase,
)


class SwitchResearchLibraryUseCase:
    """Делает научную библиотеку активной для указанного чата."""

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        bind_library: BindResearchLibraryUseCase,
    ):
        self._libraries = library_repository
        self._bind_library = bind_library

    def execute(self, agent_id: int, name: str) -> ResearchLibraryDTO:
        library = self._libraries.get_by_name(name)
        if library is None or library.id is None:
            raise ValueError(f"Научная библиотека '{name}' не найдена.")
        return self._bind_library.execute(agent_id, library.id).library
