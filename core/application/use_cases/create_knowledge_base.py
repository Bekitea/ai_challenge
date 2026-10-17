from __future__ import annotations

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.application.protocols.knowledge_base_repository import KnowledgeBaseRepository
from core.application.services.rag_model_service import RagModelService


class CreateKnowledgeBaseUseCase:
    """Use case создания базы знаний."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        rag_model_service: RagModelService,
    ):
        self._kb_repository = knowledge_base_repository
        self._model_service = rag_model_service

    def execute(self, name: str, description: str | None = None) -> KnowledgeBaseDTO:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Название базы знаний не может быть пустым")

        return self._kb_repository.create(
            name=clean_name,
            description=(description or "").strip() or None,
            embedding_model=self._model_service.embedding_model_name,
            embedding_dimension=self._model_service.embedding_dimension,
        )
