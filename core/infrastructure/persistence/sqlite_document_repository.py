from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.application.dtos.chunk_dto import ChunkDTO
from core.application.dtos.chunk_ingest import ChunkIngest
from core.application.dtos.document_dto import DocumentDTO
from core.application.dtos.document_status import (
    DOCUMENT_STATUS_PENDING,
    DOCUMENT_STATUS_READY,
)
from core.application.dtos.retrieved_chunk import RetrievedChunk
from core.infrastructure.persistence.orm import (
    ChunkORM,
    DocumentORM,
)
from core.infrastructure.persistence.sqlite_vec_vector_store import (
    SqliteVecVectorStore,
)
from core.infrastructure.persistence.vector_insert_item import VectorInsertItem


def _now() -> datetime:
    return datetime.now().astimezone()



class SqliteDocumentRepository:
    """Работа с документами и чанками базы знаний."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        vector_store: SqliteVecVectorStore,
    ):
        self._session_factory = session_factory
        self._vector_store = vector_store

    @staticmethod
    def _to_dto(orm: DocumentORM) -> DocumentDTO:
        return DocumentDTO(
            id=orm.id,
            knowledge_base_id=orm.kb_id,
            name=orm.name,
            source_type=orm.source_type,
            source_path=orm.source_path,
            status=orm.status,
            error_message=orm.error_message,
            chunk_count=orm.chunk_count,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _chunk_to_dto(orm: ChunkORM) -> ChunkDTO:
        return ChunkDTO(
            id=orm.id,
            document_id=orm.document_id,
            chunk_index=orm.chunk_index,
            text=orm.text,
            char_start=orm.char_start,
            char_end=orm.char_end,
            token_count=orm.token_count,
            created_at=orm.created_at,
        )

    def create_pending(
        self,
        kb_id: int,
        name: str,
        source_type: str,
        source_path: str | None,
        content_hash: str | None,
    ) -> int:
        with self._session_factory() as session:
            orm = DocumentORM(
                kb_id=kb_id,
                name=name,
                source_type=source_type,
                source_path=source_path,
                content_hash=content_hash,
                status=DOCUMENT_STATUS_PENDING,
                chunk_count=0,
            )
            session.add(orm)
            session.commit()
            return orm.id

    def set_status(
        self,
        document_id: int,
        status: str,
        error_message: str | None = None,
        chunk_count: int | None = None,
    ) -> None:
        with self._session_factory() as session:
            orm = session.get(DocumentORM, document_id)
            if orm is None:
                return
            orm.status = status
            if error_message is not None:
                orm.error_message = error_message
            if chunk_count is not None:
                orm.chunk_count = chunk_count
            orm.updated_at = _now()
            session.commit()

    def store_indexed(
        self,
        kb_id: int,
        document_id: int,
        chunks: Sequence[ChunkIngest],
    ) -> int:
        with self._session_factory() as session:
            orm_chunks: list[ChunkORM] = []
            for chunk in chunks:
                orm = ChunkORM(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    token_count=chunk.token_count,
                )
                session.add(orm)
                orm_chunks.append(orm)

            session.flush()

            items = [
                VectorInsertItem(chunk_orm.id, chunk.embedding)
                for chunk_orm, chunk in zip(orm_chunks, chunks, strict=True)
            ]
            self._vector_store.insert_vectors(kb_id, items, session)

            document = session.get(DocumentORM, document_id)
            if document is not None:
                document.status = DOCUMENT_STATUS_READY
                document.error_message = None
                document.chunk_count = len(orm_chunks)
                document.updated_at = _now()

            session.commit()
            return len(orm_chunks)

    def delete(self, document_id: int) -> bool:
        with self._session_factory() as session:
            orm = session.get(DocumentORM, document_id)
            if orm is None:
                return False
            self._vector_store.delete_vectors_by_document_id(
                orm.kb_id, document_id, session
            )
            session.delete(orm)
            session.commit()
            return True

    def get(self, document_id: int) -> DocumentDTO | None:
        with self._session_factory() as session:
            orm = session.get(DocumentORM, document_id)
            return self._to_dto(orm) if orm is not None else None

    def list_by_kb(self, kb_id: int) -> list[DocumentDTO]:
        with self._session_factory() as session:
            orms = (
                session.execute(
                    select(DocumentORM)
                    .where(DocumentORM.kb_id == kb_id)
                    .order_by(DocumentORM.created_at, DocumentORM.id)
                )
                .scalars()
                .all()
            )
            return [self._to_dto(orm) for orm in orms]

    def list_chunks(self, document_id: int) -> list[ChunkDTO]:
        with self._session_factory() as session:
            orms = (
                session.execute(
                    select(ChunkORM)
                    .where(ChunkORM.document_id == document_id)
                    .order_by(ChunkORM.chunk_index)
                )
                .scalars()
                .all()
            )
            return [self._chunk_to_dto(orm) for orm in orms]

    def fetch_for_search(
        self, kb_id: int, chunk_ids: Sequence[int]
    ) -> list[RetrievedChunk]:
        if not chunk_ids:
            return []
        with self._session_factory() as session:
            stmt = (
                select(
                    ChunkORM.id.label("chunk_id"),
                    ChunkORM.document_id.label("document_id"),
                    ChunkORM.chunk_index.label("chunk_index"),
                    ChunkORM.text.label("text"),
                    DocumentORM.name.label("document_name"),
                    DocumentORM.kb_id.label("kb_id"),
                )
                .join(DocumentORM, DocumentORM.id == ChunkORM.document_id)
                .where(
                    ChunkORM.id.in_(list(chunk_ids)),
                    DocumentORM.kb_id == kb_id,
                    DocumentORM.status == DOCUMENT_STATUS_READY,
                    ChunkORM.text != "",
                )
            )
            rows = session.execute(stmt).all()
            return [
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    knowledge_base_id=row.kb_id,
                    document_name=row.document_name,
                    chunk_index=row.chunk_index,
                    text=row.text,
                )
                for row in rows
            ]
