from __future__ import annotations

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository


class ListKnowledgeBasesUseCase:
    """Use case получения списка баз знаний."""

    def __init__(self, knowledge_base_repository: KnowledgeBaseRepository):
        self._kb_repository = knowledge_base_repository

    def execute(self) -> list[KnowledgeBaseDTO]:
        return self._kb_repository.list()
