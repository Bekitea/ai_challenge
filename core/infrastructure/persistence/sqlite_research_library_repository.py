from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.domain.entities.research_library import ResearchLibrary
from core.infrastructure.persistence.orm import (
    AgentResearchLibraryORM,
    ResearchArticleORM,
    ResearchLibraryORM,
)


def _now() -> datetime:
    return datetime.now().astimezone()


def _load_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]


def _dump_keywords(keywords: list[str]) -> str:
    return json.dumps(keywords, ensure_ascii=False)


class SqliteResearchLibraryRepository:
    """Репозиторий научных библиотек и активной библиотеки чата."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _to_entity(orm: ResearchLibraryORM) -> ResearchLibrary:
        return ResearchLibrary(
            id=orm.id,
            name=orm.name,
            knowledge_base_id=orm.knowledge_base_id,
            description=orm.description,
            goal=orm.goal,
            field=orm.field,
            keywords=_load_keywords(orm.keywords_json),
            year_from=orm.year_from,
            year_to=orm.year_to,
            language=orm.language,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def create(self, library: ResearchLibrary) -> ResearchLibrary:
        with self._session_factory() as session:
            orm = ResearchLibraryORM(
                name=library.name,
                knowledge_base_id=library.knowledge_base_id,
                description=library.description,
                goal=library.goal,
                field=library.field,
                keywords_json=_dump_keywords(library.keywords),
                year_from=library.year_from,
                year_to=library.year_to,
                language=library.language,
            )
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def get(self, library_id: int) -> ResearchLibrary | None:
        with self._session_factory() as session:
            orm = session.get(ResearchLibraryORM, library_id)
            return self._to_entity(orm) if orm is not None else None

    def get_by_name(self, name: str) -> ResearchLibrary | None:
        # SQLite lower() не работает с кириллицей, поэтому сравниваем
        # регистронезависимо в Python (библиотек немного).
        clean = (name or "").strip().casefold()
        if not clean:
            return None
        for library in self.list():
            if library.name.strip().casefold() == clean:
                return library
        return None

    def list(self) -> list[ResearchLibrary]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ResearchLibraryORM).order_by(ResearchLibraryORM.name)
            ).all()
            return [self._to_entity(row) for row in rows]

    def update(self, library: ResearchLibrary) -> ResearchLibrary:
        if library.id is None:
            raise ValueError("Нельзя обновить библиотеку без id.")
        with self._session_factory() as session:
            orm = session.get(ResearchLibraryORM, library.id)
            if orm is None:
                raise ValueError(f"Библиотека #{library.id} не найдена.")
            orm.name = library.name
            orm.knowledge_base_id = library.knowledge_base_id
            orm.description = library.description
            orm.goal = library.goal
            orm.field = library.field
            orm.keywords_json = _dump_keywords(library.keywords)
            orm.year_from = library.year_from
            orm.year_to = library.year_to
            orm.language = library.language
            orm.updated_at = _now()
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def delete(self, library_id: int) -> bool:
        with self._session_factory() as session:
            orm = session.get(ResearchLibraryORM, library_id)
            if orm is None:
                return False
            session.delete(orm)
            session.commit()
            return True

    def bind_agent(self, agent_id: int, library_id: int) -> None:
        with self._session_factory() as session:
            link = session.get(AgentResearchLibraryORM, agent_id)
            if link is None:
                link = AgentResearchLibraryORM(
                    agent_id=agent_id,
                    library_id=library_id,
                )
                session.add(link)
            else:
                link.library_id = library_id
                link.updated_at = _now()
            session.commit()

    def get_bound_library(self, agent_id: int) -> ResearchLibrary | None:
        with self._session_factory() as session:
            link = session.get(AgentResearchLibraryORM, agent_id)
            if link is None:
                return None
            orm = session.get(ResearchLibraryORM, link.library_id)
            return self._to_entity(orm) if orm is not None else None

    def unbind_agent(self, agent_id: int) -> bool:
        with self._session_factory() as session:
            link = session.get(AgentResearchLibraryORM, agent_id)
            if link is None:
                return False
            session.delete(link)
            session.commit()
            return True

    def list_agent_ids_for_library(self, library_id: int) -> list[int]:
        with self._session_factory() as session:
            return list(
                session.scalars(
                    select(AgentResearchLibraryORM.agent_id)
                    .where(AgentResearchLibraryORM.library_id == library_id)
                    .order_by(AgentResearchLibraryORM.agent_id)
                ).all()
            )

    def count_articles(self, library_id: int) -> int:
        with self._session_factory() as session:
            return int(
                session.scalar(
                    select(func.count(ResearchArticleORM.id)).where(
                        ResearchArticleORM.library_id == library_id
                    )
                )
                or 0
            )
