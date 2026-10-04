"""Репозитории RAG: базы знаний, документы, чанки и связи с агентами.

Репозитории получают фабрику сессий извне (см. README) и не создают
соединения самостоятельно. Для атомарности операций, затрагивающих и
реляционные таблицы, и векторные таблицы sqlite-vec, используется одна сессия.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_errors import KnowledgeBaseAlreadyExistsError
from rag_models import (
    DOCUMENT_STATUS_PENDING,
    DOCUMENT_STATUS_READY,
    ChunkDTO,
    DocumentDTO,
    KnowledgeBaseDTO,
    RetrievedChunk,
)
from storage.orm_models import (
    AgentKnowledgeBaseORM,
    ChunkORM,
    DocumentORM,
    KnowledgeBaseORM,
)
from storage.vector_store import SqliteVecVectorStore, VectorInsertItem


def _now() -> datetime:
    return datetime.now().astimezone()


@dataclass
class ChunkIngest:
    """Чанк с эмбеддингом для сохранения при индексации."""

    chunk_index: int
    text: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    embedding: Sequence[float]


class KnowledgeBaseRepository:
    """CRUD баз знаний."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        vector_store: SqliteVecVectorStore,
    ):
        self._session_factory = session_factory
        self._vector_store = vector_store

    @staticmethod
    def _to_dto(
        orm: KnowledgeBaseORM,
        document_count: int | None = None,
        chunk_count: int | None = None,
    ) -> KnowledgeBaseDTO:
        return KnowledgeBaseDTO(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            embedding_model=orm.embedding_model,
            embedding_dimension=orm.embedding_dimension,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            document_count=document_count,
            chunk_count=chunk_count,
        )

    @staticmethod
    def _all_counts(session: Session) -> dict[int, tuple[int, int]]:
        doc_counts = dict(
            session.execute(
                select(DocumentORM.kb_id, func.count(DocumentORM.id)).group_by(
                    DocumentORM.kb_id
                )
            ).all()
        )
        chunk_counts = dict(
            session.execute(
                select(DocumentORM.kb_id, func.count(ChunkORM.id))
                .join(ChunkORM, ChunkORM.document_id == DocumentORM.id)
                .group_by(DocumentORM.kb_id)
            ).all()
        )
        keys = set(doc_counts) | set(chunk_counts)
        return {
            key: (int(doc_counts.get(key, 0)), int(chunk_counts.get(key, 0)))
            for key in keys
        }

    def create(
        self,
        name: str,
        description: str | None,
        embedding_model: str,
        embedding_dimension: int,
    ) -> KnowledgeBaseDTO:
        with self._session_factory() as session:
            existing = (
                session.execute(
                    select(KnowledgeBaseORM).where(
                        func.lower(KnowledgeBaseORM.name) == name.lower()
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                raise KnowledgeBaseAlreadyExistsError(
                    f"База знаний '{name}' уже существует."
                )

            orm = KnowledgeBaseORM(
                name=name,
                description=description,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )
            session.add(orm)
            session.flush()

            try:
                self._vector_store.create_vector_table(
                    orm.id, embedding_dimension, session
                )
            except Exception:
                session.rollback()
                raise

            orm.vector_table = self._vector_store.table_name(orm.id)
            session.commit()
            return self._to_dto(orm, 0, 0)

    def get(self, kb_id: int) -> KnowledgeBaseDTO | None:
        with self._session_factory() as session:
            orm = session.get(KnowledgeBaseORM, kb_id)
            if orm is None:
                return None
            document_count, chunk_count = self._all_counts(session).get(
                kb_id, (0, 0)
            )
            return self._to_dto(orm, document_count, chunk_count)

    def list(self) -> list[KnowledgeBaseDTO]:
        with self._session_factory() as session:
            orms = (
                session.execute(
                    select(KnowledgeBaseORM).order_by(KnowledgeBaseORM.id)
                )
                .scalars()
                .all()
            )
            counts = self._all_counts(session)
            return [
                self._to_dto(orm, *counts.get(orm.id, (0, 0))) for orm in orms
            ]

    def get_embedding_metadata(
        self, kb_id: int
    ) -> tuple[str | None, str, int] | None:
        with self._session_factory() as session:
            orm = session.get(KnowledgeBaseORM, kb_id)
            if orm is None:
                return None
            return orm.vector_table, orm.embedding_model, orm.embedding_dimension

    def delete(self, kb_id: int) -> bool:
        with self._session_factory() as session:
            orm = session.get(KnowledgeBaseORM, kb_id)
            if orm is None:
                return False
            self._vector_store.drop_vector_table(kb_id, session)
            session.delete(orm)
            session.commit()
            return True


class DocumentRepository:
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


class AgentKnowledgeBaseRepository:
    """Связь агентов и подключённых к ним баз знаний."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def attach(self, agent_id: int, kb_id: int) -> bool:
        """Подключает базу знаний к агенту. Идемпотентно."""
        with self._session_factory() as session:
            existing = (
                session.execute(
                    select(AgentKnowledgeBaseORM).where(
                        AgentKnowledgeBaseORM.agent_id == agent_id,
                        AgentKnowledgeBaseORM.knowledge_base_id == kb_id,
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                return False
            session.add(
                AgentKnowledgeBaseORM(
                    agent_id=agent_id, knowledge_base_id=kb_id
                )
            )
            session.commit()
            return True

    def detach(self, agent_id: int, kb_id: int) -> bool:
        """Отключает базу знаний от агента. Идемпотентно."""
        with self._session_factory() as session:
            link = (
                session.execute(
                    select(AgentKnowledgeBaseORM).where(
                        AgentKnowledgeBaseORM.agent_id == agent_id,
                        AgentKnowledgeBaseORM.knowledge_base_id == kb_id,
                    )
                )
                .scalars()
                .first()
            )
            if link is None:
                return False
            session.delete(link)
            session.commit()
            return True

    def is_attached(self, agent_id: int, kb_id: int) -> bool:
        with self._session_factory() as session:
            return (
                session.execute(
                    select(AgentKnowledgeBaseORM.id).where(
                        AgentKnowledgeBaseORM.agent_id == agent_id,
                        AgentKnowledgeBaseORM.knowledge_base_id == kb_id,
                    )
                ).first()
                is not None
            )

    def list_kb_ids(self, agent_id: int) -> list[int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentKnowledgeBaseORM.knowledge_base_id)
                .where(AgentKnowledgeBaseORM.agent_id == agent_id)
                .order_by(AgentKnowledgeBaseORM.knowledge_base_id)
            ).all()
            return [int(row[0]) for row in rows]

    def list_for_agent(self, agent_id: int) -> list[KnowledgeBaseDTO]:
        with self._session_factory() as session:
            rows = session.execute(
                select(KnowledgeBaseORM)
                .join(
                    AgentKnowledgeBaseORM,
                    AgentKnowledgeBaseORM.knowledge_base_id == KnowledgeBaseORM.id,
                )
                .where(AgentKnowledgeBaseORM.agent_id == agent_id)
                .order_by(KnowledgeBaseORM.id)
            ).scalars().all()
            counts = KnowledgeBaseRepository._all_counts(session)
            return [
                KnowledgeBaseRepository._to_dto(orm, *counts.get(orm.id, (0, 0)))
                for orm in rows
            ]
