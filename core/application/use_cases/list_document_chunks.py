from __future__ import annotations

from core.application.dtos.chunk_dto import ChunkDTO
from core.application.protocols.document_repository import DocumentRepository


class ListDocumentChunksUseCase:
    """Use case получения чанков документа."""

    def __init__(self, document_repository: DocumentRepository):
        self._document_repository = document_repository

    def execute(self, document_id: int) -> list[ChunkDTO]:
        return self._document_repository.list_chunks(document_id)
