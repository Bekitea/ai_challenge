from __future__ import annotations

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.application.protocols.agent_knowledge_base_repository import (
    AgentKnowledgeBaseRepository,
)


class ListAgentKnowledgeBasesUseCase:
    """Use case получения баз знаний, подключённых к чату."""

    def __init__(self, agent_knowledge_base_repository: AgentKnowledgeBaseRepository):
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int) -> list[KnowledgeBaseDTO]:
        return self._agent_kb_repository.list_for_agent(agent_id)
