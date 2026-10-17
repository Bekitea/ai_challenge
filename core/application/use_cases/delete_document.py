from __future__ import annotations

from core.application.protocols.document_repository import DocumentRepository


class DeleteDocumentUseCase:
    """Use case удаления документа вместе с чанками и векторами."""

    def __init__(self, document_repository: DocumentRepository):
        self._document_repository = document_repository

    def execute(self, document_id: int) -> bool:
        return self._document_repository.delete(document_id)
