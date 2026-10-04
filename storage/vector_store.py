"""Инфраструктурный компонент работы с векторными таблицами sqlite-vec.

Вся работа с сырым SQL к виртуальным таблицам ``vec0`` инкапсулирована здесь.
Имя таблицы строится только из целочисленного id базы знаний, поэтому
подстановка идентификатора в SQL безопасна. Векторные таблицы не входят в
``Base.metadata`` и создаются/удаляются приложением.

``rowid`` в векторной таблице совпадает с ``chunks.id``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from rag_errors import VectorStoreError

logger = logging.getLogger("rag.vector_store")


@dataclass
class VectorInsertItem:
    """Вектор чанка для вставки."""

    chunk_id: int
    embedding: Sequence[float]


@dataclass
class VectorSearchItem:
    """Результат векторного поиска."""

    chunk_id: int
    distance: float


class SqliteVecVectorStore:
    """Хранилище векторов на виртуальных таблицах sqlite-vec."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def table_name(kb_id: int) -> str:
        """Формирует безопасное имя векторной таблицы базы знаний."""
        return f"vec_chunks_kb_{int(kb_id)}"

    @staticmethod
    def _quoted(table: str) -> str:
        if not table.startswith("vec_chunks_kb_"):
            raise VectorStoreError(f"Недопустимое имя векторной таблицы: {table}")
        return f'"{table}"'

    def _run(self, session: Session | None, operation: Callable[[Session], object]):
        if session is not None:
            return operation(session)
        with self._session_factory() as own_session:
            result = operation(own_session)
            own_session.commit()
            return result

    def create_vector_table(
        self,
        kb_id: int,
        dimension: int,
        session: Session | None = None,
    ) -> None:
        table = self._quoted(self.table_name(kb_id))
        sql = text(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} "
            f"USING vec0(embedding float[{int(dimension)}])"
        )

        def op(s: Session):
            try:
                s.execute(sql)
            except SQLAlchemyError as exc:
                raise VectorStoreError(
                    f"Не удалось создать векторную таблицу {table}: {exc}"
                ) from exc

        self._run(session, op)

    def drop_vector_table(self, kb_id: int, session: Session | None = None) -> None:
        table = self._quoted(self.table_name(kb_id))
        sql = text(f"DROP TABLE IF EXISTS {table}")

        def op(s: Session):
            try:
                s.execute(sql)
            except SQLAlchemyError as exc:
                raise VectorStoreError(
                    f"Не удалось удалить векторную таблицу {table}: {exc}"
                ) from exc

        self._run(session, op)

    @staticmethod
    def _serialize(item: VectorInsertItem) -> dict:
        return {
            "rowid": int(item.chunk_id),
            "emb": json.dumps([float(x) for x in item.embedding]),
        }

    def insert_vectors(
        self,
        kb_id: int,
        items: Sequence[VectorInsertItem],
        session: Session,
    ) -> None:
        if not items:
            return
        table = self._quoted(self.table_name(kb_id))
        sql = text(f"INSERT INTO {table}(rowid, embedding) VALUES (:rowid, :emb)")
        params = [self._serialize(item) for item in items]
        try:
            session.execute(sql, params)
        except SQLAlchemyError as exc:
            raise VectorStoreError(
                f"Не удалось вставить векторы в {table}: {exc}"
            ) from exc

    def delete_vectors_by_chunk_ids(
        self,
        kb_id: int,
        chunk_ids: Sequence[int],
        session: Session,
    ) -> None:
        if not chunk_ids:
            return
        table = self._quoted(self.table_name(kb_id))
        sql = text(f"DELETE FROM {table} WHERE rowid IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
        try:
            session.execute(sql, {"ids": [int(cid) for cid in chunk_ids]})
        except SQLAlchemyError as exc:
            raise VectorStoreError(
                f"Не удалось удалить векторы из {table}: {exc}"
            ) from exc

    def delete_vectors_by_document_id(
        self,
        kb_id: int,
        document_id: int,
        session: Session,
    ) -> None:
        table = self._quoted(self.table_name(kb_id))
        sql = text(
            f"DELETE FROM {table} WHERE rowid IN "
            f"(SELECT id FROM chunks WHERE document_id = :doc_id)"
        )
        try:
            session.execute(sql, {"doc_id": int(document_id)})
        except SQLAlchemyError as exc:
            raise VectorStoreError(
                f"Не удалось удалить векторы документа из {table}: {exc}"
            ) from exc

    def search(
        self,
        kb_id: int,
        query_vector: Sequence[float],
        limit: int,
        session: Session | None = None,
    ) -> list[VectorSearchItem]:
        table = self._quoted(self.table_name(kb_id))
        sql = text(
            f"SELECT rowid AS chunk_id, distance FROM {table} "
            f"WHERE embedding MATCH :vec ORDER BY distance LIMIT :limit"
        )
        params = {
            "vec": json.dumps([float(x) for x in query_vector]),
            "limit": int(limit),
        }

        def op(s: Session) -> list[VectorSearchItem]:
            try:
                rows = s.execute(sql, params).fetchall()
            except SQLAlchemyError as exc:
                raise VectorStoreError(
                    f"Ошибка векторного поиска в {table}: {exc}"
                ) from exc
            return [
                VectorSearchItem(chunk_id=int(row.chunk_id), distance=float(row.distance))
                for row in rows
            ]

        return self._run(session, op)  # type: ignore[return-value]
