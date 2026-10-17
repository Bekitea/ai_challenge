"""Детерминированный реранкер для тестового режима (без сети)."""

from __future__ import annotations

from collections.abc import Sequence

from core.application.dtos.rerank_result import RerankResult


class MockRerankerProvider:
    """Детерминированный реранкер для тестового режима (без сети)."""

    def __init__(self, model_name: str = "mock-reranker"):
        self.model_name = model_name

    @staticmethod
    def _score(query: str, document: str) -> float:
        query_tokens = set(query.lower().split())
        document_tokens = set(document.lower().split())
        if not query_tokens or not document_tokens:
            return 0.0
        overlap = len(query_tokens & document_tokens)
        return overlap / len(query_tokens)

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        results = [
            RerankResult(
                index=index,
                score=self._score(query, document),
                text=document,
            )
            for index, document in enumerate(documents)
        ]
        # Стабильная сортировка: при равных score сохраняется исходный порядок.
        results.sort(key=lambda result: result.score, reverse=True)
        if top_n is not None:
            return results[:top_n]
        return results
