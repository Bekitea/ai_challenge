from __future__ import annotations

from typing import Protocol

from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO


class KnowledgeBaseRepository(Protocol):
    """Порт репозитория баз знаний RAG."""

    def create(
        self,
        name: str,
        description: str | None,
        embedding_model: str,
        embedding_dimension: int,
    ) -> KnowledgeBaseDTO: ...

    def get(self, kb_id: int) -> KnowledgeBaseDTO | None: ...

    def list(self) -> list[KnowledgeBaseDTO]: ...

    def get_embedding_metadata(
        self, kb_id: int
    ) -> tuple[str | None, str, int] | None: ...

    def delete(self, kb_id: int) -> bool: ...
