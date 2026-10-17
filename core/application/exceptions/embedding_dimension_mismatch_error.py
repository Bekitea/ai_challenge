from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class EmbeddingDimensionMismatchError(RagError):
    """Размерность эмбеддинга не совпадает с размерностью базы знаний."""
