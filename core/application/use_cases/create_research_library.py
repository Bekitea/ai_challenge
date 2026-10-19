from __future__ import annotations

from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.protocols.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.bind_research_library import (
    BindResearchLibraryUseCase,
)
from core.application.use_cases.create_knowledge_base import (
    CreateKnowledgeBaseUseCase,
)
from core.domain.entities.research_library import ResearchLibrary
from core.domain.protocols.agent_repository import AgentRepository


class CreateResearchLibraryUseCase:
    """Создаёт научную библиотеку с собственной базой знаний и привязывает к чату."""

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        knowledge_base_repository: KnowledgeBaseRepository,
        agent_repository: AgentRepository,
        create_knowledge_base: CreateKnowledgeBaseUseCase,
        bind_library: BindResearchLibraryUseCase,
        knowledge_base_prefix: str,
    ):
        self._libraries = library_repository
        self._knowledge_bases = knowledge_base_repository
        self._agents = agent_repository
        self._create_knowledge_base = create_knowledge_base
        self._bind_library = bind_library
        self._kb_prefix = knowledge_base_prefix.strip() or "Научная библиотека"

    def execute(
        self,
        agent_id: int,
        name: str,
        *,
        description: str | None = None,
        goal: str | None = None,
        field: str | None = None,
        keywords: list[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        language: str | None = None,
    ) -> ResearchLibraryDTO:
        agent = self._agents.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Чат #{agent_id} не найден.")

        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Имя научной библиотеки не может быть пустым.")
        if self._libraries.get_by_name(clean_name) is not None:
            raise ValueError(f"Научная библиотека '{clean_name}' уже существует.")

        kb_name = self._unique_kb_name(clean_name)
        knowledge_base = self._create_knowledge_base.execute(
            kb_name,
            description or f"Научная библиотека: {clean_name}",
        )
        library = self._libraries.create(
            ResearchLibrary(
                id=None,
                name=clean_name,
                knowledge_base_id=knowledge_base.id,
                description=description,
                goal=goal,
                field=field,
                keywords=list(keywords or []),
                year_from=year_from,
                year_to=year_to,
                language=language,
            )
        )
        if library.id is None:
            raise RuntimeError("Не удалось создать научную библиотеку.")
        binding = self._bind_library.execute(agent_id, library.id)
        return binding.library

    def _unique_kb_name(self, library_name: str) -> str:
        existing = {kb.name.strip().lower() for kb in self._knowledge_bases.list()}
        base = f"{self._kb_prefix}: {library_name}"
        candidate = base
        suffix = 2
        while candidate.strip().lower() in existing:
            candidate = f"{base} ({suffix})"
            suffix += 1
        return candidate[:255]
