from __future__ import annotations

from collections.abc import Sequence

from core.application.exceptions.reranker_provider_error import RerankerProviderError
from core.application.protocols.embedding_provider import EmbeddingProvider
from core.application.protocols.reranker_provider import RerankerProvider


class RagModelService:
    """Сервис работы с моделями эмбеддинга и реранкинга."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        reranker: RerankerProvider | None = None,
    ):
        self._embedder = embedder
        self._reranker = reranker

    @property
    def embedding_model_name(self) -> str:
        return self._embedder.model_name

    @property
    def embedding_dimension(self) -> int:
        return self._embedder.dimension

    @property
    def reranker_available(self) -> bool:
        return self._reranker is not None

    def embed_query(self, query: str) -> Sequence[float]:
        return self._embedder.embed_query(query)

    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return self._embedder.embed_texts(texts)

    def rerank(
        self,
        query: str,
        candidates: Sequence[str],
        top_n: int | None = None,
    ):
        if self._reranker is None:
            raise RerankerProviderError("Реранкер не настроен.")
        return self._reranker.rerank(query, candidates, top_n)
