"""Провайдеры эмбеддингов (инфраструктурный слой).

Провайдер отвечает только за преобразование текста в вектор и ничего не знает
о базах знаний, документах и чанках.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import requests

from rag_errors import EmbeddingDimensionMismatchError, EmbeddingProviderError


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Протокол провайдера эмбеддингов."""

    model_name: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Возвращает эмбеддинги для пакета текстов."""
        ...

    def embed_query(self, text: str) -> Sequence[float]:
        """Возвращает эмбеддинг одиночного запроса."""
        ...


class OllamaEmbeddingProvider:
    """Провайдер эмбеддингов через локальный Ollama (``/api/embed``)."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        dimension: int = 1024,
        batch_size: int = 16,
        timeout: int = 60,
        retry_count: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.dimension = dimension
        self.batch_size = max(1, batch_size)
        self.timeout = timeout
        self.retry_count = max(0, retry_count)

    def _request_batch(self, texts: Sequence[str]) -> list[list[float]]:
        url = f"{self.base_url}/api/embed"
        payload = {"model": self.model_name, "input": list(texts)}
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")
                if embeddings is None and "embedding" in data:
                    embeddings = [data["embedding"]]
                if embeddings is None:
                    raise EmbeddingProviderError(
                        "Ollama не вернул эмбеддинги в ответе."
                    )
                return [list(map(float, vector)) for vector in embeddings]
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    time.sleep(0.5 * (attempt + 1))
        raise EmbeddingProviderError(
            f"Не удалось получить эмбеддинги от Ollama ({self.model_name}): {last_error}"
        )

    def _validate_dimension(self, vectors: Sequence[Sequence[float]]) -> None:
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingDimensionMismatchError(
                    f"Ожидалась размерность {self.dimension}, получена {len(vector)}."
                )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        result: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = list(texts[start : start + self.batch_size])
            vectors = self._request_batch(batch)
            self._validate_dimension(vectors)
            result.extend(vectors)
        return result

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        if not vectors:
            raise EmbeddingProviderError("Пустой текст запроса.")
        return vectors[0]
