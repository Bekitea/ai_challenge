from __future__ import annotations

from dataclasses import dataclass

from core.application.dtos.document_dto import DocumentDTO
from core.application.dtos.document_status import DOCUMENT_STATUS_ERROR
from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO


@dataclass
class ProjectKnowledgeBaseSeedResult:
    """Итог засева проектной базы знаний (README + docs)."""

    knowledge_base: KnowledgeBaseDTO
    documents: list[DocumentDTO]
    removed_count: int
    skipped_paths: list[str]

    @property
    def ready_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status != DOCUMENT_STATUS_ERROR)

    @property
    def error_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status == DOCUMENT_STATUS_ERROR)
