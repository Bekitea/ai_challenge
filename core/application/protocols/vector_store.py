from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from core.application.dtos.vector_search_item import VectorSearchItem


class VectorStore(Protocol):
    """Порт векторного хранилища, доступный приложению (RAG-поиск)."""

    def search(
        self,
        kb_id: int,
        query_vector: Sequence[float],
        limit: int,
    ) -> list[VectorSearchItem]:
        """Возвращает ближайшие чанки базы знаний к вектору запроса."""
        ...
