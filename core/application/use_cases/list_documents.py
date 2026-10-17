from __future__ import annotations

from core.application.dtos.document_dto import DocumentDTO
from core.application.exceptions.knowledge_base_not_found_error import (
    KnowledgeBaseNotFoundError,
)
from core.application.protocols.document_repository import DocumentRepository
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository


class ListDocumentsUseCase:
    """Use case получения списка документов базы знаний."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository

    def execute(self, knowledge_base_id: int) -> list[DocumentDTO]:
        if self._kb_repository.get(knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError(
                f"База знаний #{knowledge_base_id} не найдена."
            )
        return self._document_repository.list_by_kb(knowledge_base_id)
