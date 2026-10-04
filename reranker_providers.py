"""Провайдеры реранкинга (инфраструктурный слой).

На старте реранкер отключён (``RERANKER_ENABLED=false``), поэтому здесь
описан только протокол и DTO результата. Реализацию можно добавить позже,
подключив её в фабрике приложения, без изменения прикладного слоя.

Примечание: у Ollama нет штатного API реранкинга (``/api/rerank``), поэтому
при реализации потребуется отдельный сервис (например, sentence-transformers).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class RerankResult:
    """Результат реранкинга одного документа."""

    index: int
    score: float
    text: str | None = None


@runtime_checkable
class RerankerProvider(Protocol):
    """Протокол провайдера реранкера."""

    model_name: str

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> Sequence[RerankResult]:
        """Переупорядочивает документы по релевантности запросу."""
        ...
