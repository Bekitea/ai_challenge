from __future__ import annotations

from core.application.dtos.research_library_operation_result_dto import (
    ResearchLibraryOperationResultDTO,
)
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.detach_knowledge_base_from_agent import (
    DetachKnowledgeBaseFromAgentUseCase,
)


class DetachResearchLibraryUseCase:
    """Открепляет активную научную библиотеку от чата.

    Библиотека, её статьи и БЗ сохраняются и могут быть подключены к другому
    чату. От чата отключается только БЗ этой библиотеки.
    """

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        detach_knowledge_base: DetachKnowledgeBaseFromAgentUseCase,
    ):
        self._libraries = library_repository
        self._detach_kb = detach_knowledge_base

    def execute(self, agent_id: int) -> ResearchLibraryOperationResultDTO:
        library = self._libraries.get_bound_library(agent_id)
        if library is None or library.id is None:
            return ResearchLibraryOperationResultDTO(
                success=False,
                message="У чата нет активной научной библиотеки.",
            )

        if library.knowledge_base_id is not None:
            self._detach_kb.execute(agent_id, library.knowledge_base_id)
        self._libraries.unbind_agent(agent_id)

        dto = research_library_to_dto(library)
        dto.article_count = self._libraries.count_articles(library.id)
        return ResearchLibraryOperationResultDTO(
            success=True,
            message=(
                f"Научная библиотека '{library.name}' откреплена от чата. "
                "Сама библиотека и её статьи сохранены."
            ),
            library=dto,
            affected_chats=1,
        )
