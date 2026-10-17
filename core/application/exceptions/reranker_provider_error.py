from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class RerankerProviderError(RagError):
    """Ошибка провайдера реранкера."""
