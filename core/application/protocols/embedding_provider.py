from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Порт провайдера эмбеддингов."""

    model_name: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Возвращает эмбеддинги для пакета текстов."""
        ...

    def embed_query(self, text: str) -> Sequence[float]:
        """Возвращает эмбеддинг одиночного запроса."""
        ...
