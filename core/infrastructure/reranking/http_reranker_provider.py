"""Провайдер реранкинга через внешний HTTP-сервис (``POST /rerank``)."""

from __future__ import annotations

import time
from collections.abc import Sequence

import requests

from core.application.dtos.rerank_result import RerankResult
from core.application.exceptions.reranker_provider_error import RerankerProviderError


class HttpRerankerProvider:
    """Провайдер реранкинга через внешний HTTP-сервис (``POST /rerank``)."""

    def __init__(
        self,
        base_url: str,
        model_name: str = "bge-reranker-v2-m3",
        batch_size: int = 32,
        timeout: int = 60,
        retry_count: int = 1,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.retry_count = max(0, retry_count)

    def _request_batch(
        self, query: str, documents: Sequence[str]
    ) -> list[dict]:
        url = f"{self.base_url}/rerank"
        payload = {
            "query": query,
            "texts": list(documents),
            "raw_scores": False,
        }
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict):
                    data = data.get("results")
                if not isinstance(data, list):
                    raise RerankerProviderError(
                        "Сервис реранкинга вернул неожиданный формат ответа."
                    )
                return data
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    time.sleep(0.5 * (attempt + 1))
        raise RerankerProviderError(
            f"Сервис реранкинга недоступен ({self.base_url}): {last_error}"
        )

    def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> list[RerankResult]:
        if not documents:
            return []

        results: list[RerankResult] = []
        for start in range(0, len(documents), self.batch_size):
            batch = list(documents[start : start + self.batch_size])
            raw = self._request_batch(query, batch)
            for item in raw:
                try:
                    local_index = int(item["index"])
                    score = float(item["score"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RerankerProviderError(
                        "Некорректный элемент в ответе сервиса реранкинга."
                    ) from exc
                if 0 <= local_index < len(batch):
                    results.append(
                        RerankResult(
                            index=start + local_index,
                            score=score,
                            text=item.get("text"),
                        )
                    )

        results.sort(key=lambda result: result.score, reverse=True)
        if top_n is not None:
            return results[:top_n]
        return results
