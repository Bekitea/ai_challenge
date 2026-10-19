from __future__ import annotations

from core.application.dtos.research_review_context_dto import (
    ResearchHypothesisContextDTO,
)
from core.application.use_cases.build_review_context import (
    BuildReviewContextUseCase,
)
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)
from core.application.use_cases.search_research_library import (
    SearchResearchLibraryUseCase,
)


class BuildHypothesisContextUseCase:
    """Собирает профиль, сводки статей и RAG-фрагменты для генерации гипотез."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        build_review_context: BuildReviewContextUseCase,
        search_library: SearchResearchLibraryUseCase,
    ):
        self._ensure_library = ensure_library
        self._build_review = build_review_context
        self._search = search_library

    def execute(
        self,
        agent_id: int,
        *,
        goal: str | None = None,
        max_chars: int = 40000,
        limit: int = 30,
        library_name: str | None = None,
    ) -> ResearchHypothesisContextDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        clean_goal = (goal or "").strip() or library.goal or None
        topic = clean_goal or library.field or library.name

        review = self._build_review.execute(
            agent_id,
            topic=topic,
            year_from=library.year_from,
            year_to=library.year_to,
            max_chars=max_chars,
            limit=limit,
            library_name=library_name,
        )

        passages: list[str] = []
        try:
            hits = self._search.execute(
                agent_id,
                topic,
                top_k=10,
                library_name=library_name,
            )
            for hit in hits.hits:
                if not hit.text.strip():
                    continue
                citation = hit.title
                if hit.publication_year:
                    citation += f" ({hit.publication_year})"
                passages.append(f"[{citation}] {hit.text.strip()}")
        except Exception:  # noqa: BLE001 - контекст гипотез не должен падать
            passages = []

        return ResearchHypothesisContextDTO(
            library=library,
            goal=clean_goal,
            articles=review.articles,
            passages=passages,
            truncated=review.truncated,
        )
