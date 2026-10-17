from __future__ import annotations

from typing import Protocol

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO


class AgentKnowledgeBaseRepository(Protocol):
    """Порт связи агентов и подключённых к ним баз знаний."""

    def attach(self, agent_id: int, kb_id: int) -> bool:
        """Подключает базу знаний к агенту. Идемпотентно."""
        ...

    def detach(self, agent_id: int, kb_id: int) -> bool:
        """Отключает базу знаний от агента. Идемпотентно."""
        ...

    def is_attached(self, agent_id: int, kb_id: int) -> bool: ...

    def list_kb_ids(self, agent_id: int) -> list[int]: ...

    def list_for_agent(self, agent_id: int) -> list[KnowledgeBaseDTO]: ...
