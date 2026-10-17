from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from core.application.dtos.chunk_dto import ChunkDTO
from core.application.dtos.chunk_ingest import ChunkIngest
from core.application.dtos.document_dto import DocumentDTO
from core.application.dtos.retrieved_chunk import RetrievedChunk


class DocumentRepository(Protocol):
    """Порт репозитория документов и чанков базы знаний RAG."""

    def create_pending(
        self,
        kb_id: int,
        name: str,
        source_type: str,
        source_path: str | None,
        content_hash: str | None,
    ) -> int: ...

    def set_status(
        self,
        document_id: int,
        status: str,
        error_message: str | None = None,
        chunk_count: int | None = None,
    ) -> None: ...

    def store_indexed(
        self,
        kb_id: int,
        document_id: int,
        chunks: Sequence[ChunkIngest],
    ) -> int: ...

    def delete(self, document_id: int) -> bool: ...

    def get(self, document_id: int) -> DocumentDTO | None: ...

    def list_by_kb(self, kb_id: int) -> list[DocumentDTO]: ...

    def list_chunks(self, document_id: int) -> list[ChunkDTO]: ...

    def fetch_for_search(
        self, kb_id: int, chunk_ids: Sequence[int]
    ) -> list[RetrievedChunk]: ...
