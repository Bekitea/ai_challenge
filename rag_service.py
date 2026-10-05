"""Прикладной сервис RAG: эмбеддинг, реранкинг и сбор контекста.

``RagModelService`` работает только через протоколы ``EmbeddingProvider`` и
``RerankerProvider`` и не знает о конкретной реализации (Ollama и т.п.).

``RagService`` выполняет поиск по подключённым к агенту базам знаний:
эмбеддинг запроса, векторный поиск, при необходимости реранкинг и ограничение
числа чанков.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence

from embedding_providers import EmbeddingProvider
from rag_errors import EmbeddingDimensionMismatchError, RerankerProviderError
from rag_models import RagContextChunk, RagRetrievalResult
from reranker_providers import RerankerProvider
from storage.rag_repositories import (
    AgentKnowledgeBaseRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from storage.vector_store import SqliteVecVectorStore

logger = logging.getLogger("rag.service")


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

    def embed_documents(
        self, texts: Sequence[str]
    ) -> Sequence[Sequence[float]]:
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


class RagService:
    """Сбор релевантного контекста из подключённых к агенту баз знаний."""

    def __init__(
        self,
        model_service: RagModelService,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        agent_knowledge_base_repository: AgentKnowledgeBaseRepository,
        vector_store: SqliteVecVectorStore,
        vector_top_k_per_kb: int = 20,
        candidate_limit_total: int = 60,
        final_top_k: int = 5,
        reranker_enabled: bool = False,
        relevance_threshold: float | None = None,
    ):
        self._model_service = model_service
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository
        self._agent_kb_repository = agent_knowledge_base_repository
        self._vector_store = vector_store
        self._vector_top_k_per_kb = vector_top_k_per_kb
        self._candidate_limit_total = candidate_limit_total
        self._final_top_k = final_top_k
        self._reranker_enabled = reranker_enabled
        self._relevance_threshold = relevance_threshold
        # Circuit breaker: после первой ошибки провайдера не пытаемся
        # реранжить до перезапуска процесса (сервис реранкинга может быть
        # не запущен — не тормозим каждый запрос сетевыми таймаутами).
        self._reranker_unavailable = False

    def retrieve(
        self,
        agent_id: int | None,
        query_text: str,
        max_candidates: int | None = None,
        final_top_k: int | None = None,
        reranker_enabled: bool | None = None,
    ) -> RagRetrievalResult:
        """Возвращает релевантные чанки по подключённым базам знаний агента.

        ``reranker_enabled`` задаёт per-chat флаг: ``None`` — использовать
        глобальный дефолт (``RERANKER_ENABLED``). Если у агента нет
        подключённых баз знаний, возвращает пустой результат, НЕ выполняя
        эмбеддинг запроса и реранкинг. Чанки с релевантностью ниже
        ``relevance_threshold`` отбрасываются.
        """
        if agent_id is None or not query_text.strip():
            return RagRetrievalResult(chunks=[], has_knowledge_bases=False)

        kb_ids = self._agent_kb_repository.list_kb_ids(agent_id)
        if not kb_ids:
            return RagRetrievalResult(chunks=[], has_knowledge_bases=False)

        candidate_limit = max_candidates or self._candidate_limit_total
        top_k = final_top_k or self._final_top_k
        per_kb = max(
            1, min(self._vector_top_k_per_kb, candidate_limit // len(kb_ids))
        )

        query_vector = self._model_service.embed_query(query_text)

        candidates: dict[int, RagContextChunk] = {}
        for kb_id in kb_ids:
            metadata = self._kb_repository.get_embedding_metadata(kb_id)
            if metadata is None:
                continue
            _table, _model, dimension = metadata
            if dimension != self._model_service.embedding_dimension:
                logger.debug(
                    "Пропуск базы знаний %s: размерность %s != %s",
                    kb_id,
                    dimension,
                    self._model_service.embedding_dimension,
                )
                continue

            hits = self._vector_store.search(kb_id, query_vector, per_kb)
            if not hits:
                continue

            distances = {hit.chunk_id: hit.distance for hit in hits}
            rows = self._document_repository.fetch_for_search(
                kb_id, [hit.chunk_id for hit in hits]
            )
            for row in rows:
                if row.chunk_id in candidates:
                    continue
                candidates[row.chunk_id] = RagContextChunk(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    knowledge_base_id=row.knowledge_base_id,
                    document_name=row.document_name,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    vector_distance=distances.get(row.chunk_id),
                )
            if len(candidates) >= candidate_limit:
                break

        chunks = list(candidates.values())
        was_empty = not chunks

        use_reranker = (
            self._reranker_enabled if reranker_enabled is None else reranker_enabled
        )
        if (
            use_reranker
            and not self._reranker_unavailable
            and self._model_service.reranker_available
        ):
            try:
                reranked = self._model_service.rerank(
                    query_text, [chunk.text for chunk in chunks], top_n=top_k
                )
                ordered: list[RagContextChunk] = []
                for result in reranked:
                    if 0 <= result.index < len(chunks):
                        chunk = chunks[result.index]
                        chunk.rerank_score = result.score
                        ordered.append(chunk)
                return self._finalize_result(ordered, was_empty, top_k)
            except RerankerProviderError:
                self._reranker_unavailable = True
                logger.warning(
                    "Реранкинг недоступен, переходим к векторному порядку",
                    exc_info=True,
                )

        chunks.sort(
            key=lambda chunk: (
                chunk.vector_distance
                if chunk.vector_distance is not None
                else math.inf
            )
        )
        return self._finalize_result(chunks, was_empty, top_k)

    def _finalize_result(
        self,
        ordered: list[RagContextChunk],
        was_empty: bool,
        top_k: int,
    ) -> RagRetrievalResult:
        """Применяет порог релевантности и формирует итог поиска."""
        filtered = [
            chunk
            for chunk in ordered
            if self._relevance_threshold is None
            or chunk.relevance is None
            or chunk.relevance >= self._relevance_threshold
        ]
        return RagRetrievalResult(
            chunks=filtered[:top_k],
            has_knowledge_bases=True,
            below_threshold=not filtered and not was_empty,
        )

    def search_knowledge_base(
        self,
        knowledge_base_id: int,
        query_text: str,
        top_k: int | None = None,
    ) -> list[RagContextChunk]:
        """Поиск по одной базе знаний (используется в меню управления)."""
        metadata = self._kb_repository.get_embedding_metadata(knowledge_base_id)
        if metadata is None:
            return []
        _table, _model, dimension = metadata
        if dimension != self._model_service.embedding_dimension:
            raise EmbeddingDimensionMismatchError(
                "Размерность эмбеддингов базы знаний не совпадает с "
                "размерностью текущей модели."
            )

        query_vector = self._model_service.embed_query(query_text)
        hits = self._vector_store.search(
            knowledge_base_id, query_vector, self._vector_top_k_per_kb
        )
        distances = {hit.chunk_id: hit.distance for hit in hits}
        rows = self._document_repository.fetch_for_search(
            knowledge_base_id, list(distances)
        )
        chunks = [
            RagContextChunk(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                knowledge_base_id=row.knowledge_base_id,
                document_name=row.document_name,
                chunk_index=row.chunk_index,
                text=row.text,
                vector_distance=distances.get(row.chunk_id),
            )
            for row in rows
        ]
        chunks.sort(
            key=lambda chunk: (
                chunk.vector_distance
                if chunk.vector_distance is not None
                else math.inf
            )
        )
        return chunks[: (top_k or self._final_top_k)]
