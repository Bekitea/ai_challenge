from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class AgentNotFoundError(RagError):
    """Агент не найден."""
