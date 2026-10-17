from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class KnowledgeBaseNotAttachedError(RagError):
    """База знаний не подключена к агенту."""
