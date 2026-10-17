from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from core.application.dtos.rerank_result import RerankResult


@runtime_checkable
class RerankerProvider(Protocol):
    """Порт провайдера реранкера."""

    model_name: str

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> Sequence[RerankResult]:
        """Переупорядочивает документы по релевантности запросу."""
        ...
