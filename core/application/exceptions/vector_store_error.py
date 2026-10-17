from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class VectorStoreError(RagError):
    """Ошибка работы с векторным хранилищем sqlite-vec."""
