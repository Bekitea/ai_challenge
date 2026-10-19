from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.research_library_dto import ResearchLibraryDTO


@dataclass
class ResearchLibraryBindingResultDTO:
    """Результат привязки научной библиотеки к чату."""

    library: ResearchLibraryDTO
    knowledge_base_attached: bool = False
    previous_library_detached: bool = False
    messages: list[str] = field(default_factory=list)
