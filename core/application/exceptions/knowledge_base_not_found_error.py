from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class KnowledgeBaseNotFoundError(RagError):
    """База знаний не найдена."""
