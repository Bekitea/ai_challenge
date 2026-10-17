from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class KnowledgeBaseAlreadyExistsError(RagError):
    """База знаний с таким названием уже существует."""
