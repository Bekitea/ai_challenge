from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.infrastructure.persistence.orm import (
    AgentKnowledgeBaseORM,
    KnowledgeBaseORM,
)


def _now() -> datetime:
    return datetime.now().astimezone()



from core.infrastructure.persistence.sqlite_knowledge_base_repository import (
    SqliteKnowledgeBaseRepository,
)


class SqliteAgentKnowledgeBaseRepository:
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
            counts = SqliteKnowledgeBaseRepository._all_counts(session)
            return [
                SqliteKnowledgeBaseRepository._to_dto(orm, *counts.get(orm.id, (0, 0)))
                for orm in rows
            ]
