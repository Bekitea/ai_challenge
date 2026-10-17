from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.application.exceptions.knowledge_base_already_exists_error import (
    KnowledgeBaseAlreadyExistsError,
)
from core.infrastructure.persistence.orm import (
    ChunkORM,
    DocumentORM,
    KnowledgeBaseORM,
)
from core.infrastructure.persistence.sqlite_vec_vector_store import (
    SqliteVecVectorStore,
)


def _now() -> datetime:
    return datetime.now().astimezone()



class SqliteKnowledgeBaseRepository:
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
