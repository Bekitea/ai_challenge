from __future__ import annotations

from core.application.dtos.research_binding_result_dto import (
    ResearchLibraryBindingResultDTO,
)
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.attach_knowledge_base_to_agent import (
    AttachKnowledgeBaseToAgentUseCase,
)
from core.application.use_cases.detach_knowledge_base_from_agent import (
    DetachKnowledgeBaseFromAgentUseCase,
)


class BindResearchLibraryUseCase:
    """Привязывает библиотеку к чату вместе с её базой знаний.

    Если у чата была другая библиотека, отвязывает только её БЗ (ручные
    привязки через /rag не трогаются). При ``auto_attach_kb`` идемпотентно
    прикрепляет БЗ новой библиотеки, чтобы обычный RAG работал вместе с
    research-инструментами.
    """

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        attach_knowledge_base: AttachKnowledgeBaseToAgentUseCase,
        detach_knowledge_base: DetachKnowledgeBaseFromAgentUseCase,
        auto_attach_kb: bool = True,
    ):
        self._libraries = library_repository
        self._attach_kb = attach_knowledge_base
        self._detach_kb = detach_knowledge_base
        self._auto_attach = auto_attach_kb

    def execute(
        self, agent_id: int, library_id: int
    ) -> ResearchLibraryBindingResultDTO:
        target = self._libraries.get(library_id)
        if target is None or target.id is None:
            raise ValueError(f"Научная библиотека #{library_id} не найдена.")

        messages: list[str] = []
        previous_detached = False
        previous = self._libraries.get_bound_library(agent_id)
        if (
            previous is not None
            and previous.id is not None
            and previous.id != library_id
            and previous.knowledge_base_id is not None
        ):
            self._detach_kb.execute(agent_id, previous.knowledge_base_id)
            previous_detached = True
            messages.append(
                f"База знаний предыдущей библиотеки '{previous.name}' "
                "отключена от чата."
            )

        self._libraries.bind_agent(agent_id, library_id)
        messages.append(f"Научная библиотека '{target.name}' подключена к чату.")

        kb_attached = False
        if self._auto_attach and target.knowledge_base_id is not None:
            success, message = self._attach_kb.execute(
                agent_id, target.knowledge_base_id
            )
            kb_attached = bool(success)
            messages.append(message)

        dto = research_library_to_dto(target)
        dto.article_count = self._libraries.count_articles(library_id)
        return ResearchLibraryBindingResultDTO(
            library=dto,
            knowledge_base_attached=kb_attached,
            previous_library_detached=previous_detached,
            messages=messages,
        )
