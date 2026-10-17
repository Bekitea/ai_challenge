from __future__ import annotations

from core.application.protocols.agent_knowledge_base_repository import (
    AgentKnowledgeBaseRepository,
)
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository


class AttachKnowledgeBaseToAgentUseCase:
    """Use case подключения базы знаний к чату (агенту)."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        agent_knowledge_base_repository: AgentKnowledgeBaseRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int, knowledge_base_id: int) -> tuple[bool, str]:
        kb = self._kb_repository.get(knowledge_base_id)
        if kb is None:
            return False, f"База знаний #{knowledge_base_id} не найдена."

        created = self._agent_kb_repository.attach(agent_id, knowledge_base_id)
        if created:
            return True, f"База знаний '{kb.name}' подключена к чату."
        return True, f"База знаний '{kb.name}' уже подключена к чату."
