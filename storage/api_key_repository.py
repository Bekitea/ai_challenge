"""Репозиторий API-ключей доступа к REST API.

Репозиторий получает фабрику сессий извне (см. README) и не создаёт
соединения самостоятельно. Наружу отдаются только метаданные ключа
(``ApiKeyRecord``); сам секрет в БД не хранится — лишь его хеш.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from storage.orm_models import ApiKeyORM


@dataclass
class ApiKeyRecord:
    """Метаданные API-ключа (без секрета)."""

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


class DatabaseApiKeyRepository:
    """CRUD API-ключей в SQLite."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _to_record(orm: ApiKeyORM) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=orm.id,
            name=orm.name,
            prefix=orm.prefix,
            created_at=orm.created_at,
            last_used_at=orm.last_used_at,
        )

    def create(self, name: str, key_hash: str, prefix: str) -> ApiKeyRecord:
        with self._session_factory() as session:
            orm = ApiKeyORM(
                name=name,
                key_hash=key_hash,
                prefix=prefix,
                created_at=datetime.now().astimezone(),
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return self._to_record(orm)

    def list_all(self) -> list[ApiKeyRecord]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ApiKeyORM).order_by(ApiKeyORM.created_at)
            ).all()
            return [self._to_record(row) for row in rows]

    def delete(self, key_id: int) -> ApiKeyRecord | None:
        with self._session_factory() as session:
            orm = session.get(ApiKeyORM, key_id)
            if orm is None:
                return None
            record = self._to_record(orm)
            session.delete(orm)
            session.commit()
            return record

    def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        with self._session_factory() as session:
            orm = session.scalar(
                select(ApiKeyORM).where(ApiKeyORM.key_hash == key_hash)
            )
            return self._to_record(orm) if orm is not None else None

    def touch(self, key_id: int) -> None:
        with self._session_factory() as session:
            orm = session.get(ApiKeyORM, key_id)
            if orm is None:
                return
            orm.last_used_at = datetime.now().astimezone()
            session.commit()
