from __future__ import annotations

from pathlib import Path

from core.application.dtos.project_kb_seed_result import ProjectKnowledgeBaseSeedResult
from core.application.protocols.document_repository import DocumentRepository
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository
from core.application.use_cases.add_document_to_knowledge_base import (
    AddDocumentToKnowledgeBaseUseCase,
)
from core.application.use_cases.create_knowledge_base import (
    CreateKnowledgeBaseUseCase,
)


class SeedProjectKnowledgeBaseUseCase:
    """Засевает выделенную базу знаний документацией проекта.

    Находит (или создаёт) базу знаний с фиксированным именем, полностью
    очищает её от прежних документов (чтобы не оставалось устаревшей
    информации) и заново индексирует README/docs проекта.
    """

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        add_document_use_case: AddDocumentToKnowledgeBaseUseCase,
        create_knowledge_base_use_case: CreateKnowledgeBaseUseCase,
        knowledge_base_name: str,
        source_paths: list[str],
        knowledge_base_description: str = "Документация проекта (README, docs).",
    ):
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository
        self._add_document = add_document_use_case
        self._create_knowledge_base = create_knowledge_base_use_case
        self._kb_name = knowledge_base_name
        self._source_paths = source_paths
        self._kb_description = knowledge_base_description

    def execute(self) -> ProjectKnowledgeBaseSeedResult:
        kb = self._find_by_name() or self._create_knowledge_base.execute(
            self._kb_name, self._kb_description
        )

        removed_count = self._purge(kb.id)

        documents = []
        skipped_paths: list[str] = []
        for source_path in self._source_paths:
            if not Path(source_path).exists():
                skipped_paths.append(source_path)
                continue
            result = self._add_document.execute(kb.id, source_path)
            documents.extend(result.documents)

        refreshed = self._kb_repository.get(kb.id) or kb
        return ProjectKnowledgeBaseSeedResult(
            knowledge_base=refreshed,
            documents=documents,
            removed_count=removed_count,
            skipped_paths=skipped_paths,
        )

    def _find_by_name(self):
        for kb in self._kb_repository.list():
            if kb.name == self._kb_name:
                return kb
        return None

    def _purge(self, kb_id: int) -> int:
        removed = 0
        for document in self._document_repository.list_by_kb(kb_id):
            if self._document_repository.delete(document.id):
                removed += 1
        return removed
