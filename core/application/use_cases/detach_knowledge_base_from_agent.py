from __future__ import annotations

from core.application.protocols.agent_knowledge_base_repository import (
    AgentKnowledgeBaseRepository,
)
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository


class DetachKnowledgeBaseFromAgentUseCase:
    """Use case отключения базы знаний от чата (агента)."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        agent_knowledge_base_repository: AgentKnowledgeBaseRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int, knowledge_base_id: int) -> tuple[bool, str]:
        kb = self._kb_repository.get(knowledge_base_id)
        name = kb.name if kb is not None else f"#{knowledge_base_id}"

        removed = self._agent_kb_repository.detach(agent_id, knowledge_base_id)
        if removed:
            return True, f"База знаний '{name}' отключена от чата."
        return True, f"База знаний '{name}' не была подключена к чату."
