from __future__ import annotations

from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository


class DeleteKnowledgeBaseUseCase:
    """Use case удаления базы знаний."""

    def __init__(self, knowledge_base_repository: KnowledgeBaseRepository):
        self._kb_repository = knowledge_base_repository

    def execute(self, knowledge_base_id: int) -> bool:
        return self._kb_repository.delete(knowledge_base_id)
