from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class DocumentIndexingError(RagError):
    """Ошибка индексации документа."""
