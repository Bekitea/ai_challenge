from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.application.dtos.research_library_operation_result_dto import (
    ResearchLibraryOperationResultDTO,
)
from core.application.mappers.research_mapper import research_library_to_dto
from core.application.protocols.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.protocols.research_library_repository import (
    ResearchLibraryRepository,
)
from core.application.use_cases.delete_knowledge_base import (
    DeleteKnowledgeBaseUseCase,
)
from core.application.use_cases.detach_knowledge_base_from_agent import (
    DetachKnowledgeBaseFromAgentUseCase,
)

logger = logging.getLogger("research.library.delete")


class DeleteResearchLibraryUseCase:
    """Полностью удаляет научную библиотеку: привязки, статьи, БЗ и файлы.

    Операция необратима и затрагивает все чаты, использующие библиотеку,
    поэтому требует точного подтверждения именем.
    """

    def __init__(
        self,
        library_repository: ResearchLibraryRepository,
        article_repository: ResearchArticleRepository,
        knowledge_base_repository: KnowledgeBaseRepository,
        detach_knowledge_base: DetachKnowledgeBaseFromAgentUseCase,
        delete_knowledge_base: DeleteKnowledgeBaseUseCase,
        data_dir: str,
    ):
        self._libraries = library_repository
        self._articles = article_repository
        self._knowledge_bases = knowledge_base_repository
        self._detach_kb = detach_knowledge_base
        self._delete_kb = delete_knowledge_base
        self._data_dir = data_dir

    def execute(
        self, name: str, confirm_name: str
    ) -> ResearchLibraryOperationResultDTO:
        library = self._libraries.get_by_name(name)
        if library is None or library.id is None:
            raise ValueError(f"Научная библиотека '{name}' не найдена.")
        if (confirm_name or "").strip() != library.name:
            raise ValueError(
                "Подтверждение не совпадает с именем библиотеки. "
                "Удаление отменено."
            )

        agent_ids = self._libraries.list_agent_ids_for_library(library.id)
        kb_id = library.knowledge_base_id
        article_count = self._articles.count(library.id)
        document_count = 0
        if kb_id is not None:
            kb = self._knowledge_bases.get(kb_id)
            document_count = kb.document_count or 0 if kb is not None else 0

        for agent_id in agent_ids:
            if kb_id is not None:
                self._detach_kb.execute(agent_id, kb_id)
            self._libraries.unbind_agent(agent_id)

        if kb_id is not None:
            self._delete_kb.execute(kb_id)

        dto = research_library_to_dto(library)
        dto.article_count = article_count
        deleted = self._libraries.delete(library.id)
        if not deleted:
            raise RuntimeError(
                f"Не удалось удалить запись библиотеки '{library.name}'."
            )

        self._delete_files(library.id)

        return ResearchLibraryOperationResultDTO(
            success=True,
            message=(
                f"Научная библиотека '{library.name}' удалена: "
                f"статей — {article_count}, документов — {document_count}, "
                f"чатов отвязано — {len(agent_ids)}."
            ),
            library=dto,
            affected_chats=len(agent_ids),
            deleted_articles=article_count,
            deleted_documents=document_count,
        )

    def _delete_files(self, library_id: int) -> None:
        path = Path(self._data_dir) / f"library_{library_id}"
        if not path.exists():
            return
        try:
            shutil.rmtree(path)
        except OSError as exc:
            logger.warning("Не удалось удалить файлы библиотеки %s: %s", path, exc)
