from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.bind_research_library import (
    BindResearchLibraryUseCase,
)
from core.application.use_cases.create_research_library import (
    CreateResearchLibraryUseCase,
)
from core.domain.protocols.agent_repository import AgentRepository


class EnsureResearchLibraryUseCase:
    """Возвращает активную библиотеку чата, создавая её при первом обращении."""

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        agent_repository: AgentRepository,
        create_library: CreateResearchLibraryUseCase,
        bind_library: BindResearchLibraryUseCase,
        auto_name_prefix: str,
    ):
        self._libraries = library_repository
        self._agents = agent_repository
        self._create_library = create_library
        self._bind_library = bind_library
        self._auto_name_prefix = auto_name_prefix.strip() or "Исследования"

    def execute(
        self, agent_id: int, library_name: str | None = None
    ) -> ResearchLibraryDTO:
        if library_name:
            library = self._libraries.get_by_name(library_name)
            if library is None:
                raise ValueError(f"Научная библиотека '{library_name}' не найдена.")
            if library.id is None:
                raise RuntimeError("Научная библиотека без id.")
            return self._bind_library.execute(agent_id, library.id).library

        bound = self._libraries.get_bound_library(agent_id)
        if bound is not None and bound.id is not None:
            # Повторная привязка идемпотентна и заодно восстанавливает
            # автопривязку БЗ для обычного RAG.
            return self._bind_library.execute(agent_id, bound.id).library

        agent = self._agents.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Чат #{agent_id} не найден.")
        auto_name = self._unique_name(
            f"{self._auto_name_prefix}: {agent.name} (#{agent_id})"
        )
        return self._create_library.execute(
            agent_id,
            auto_name,
            description=(
                "Научная библиотека, автоматически созданная для этого чата. "
                "Переименуйте и заполните профиль через research-инструменты."
            ),
        )

    def _unique_name(self, base: str) -> str:
        candidate = base[:255]
        suffix = 2
        while self._libraries.get_by_name(candidate) is not None:
            candidate = f"{base} ({suffix})"[:255]
            suffix += 1
        return candidate
