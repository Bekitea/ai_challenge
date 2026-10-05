"""Тесты релевантности RAG: единая шкала и фильтрация по порогу.

Проверка чистой логики без сети: property ``RagContextChunk.relevance`` и
поведение ``RagService.retrieve`` при пороге ``RAG_RELEVANCE_THRESHOLD``.
"""

import os
import sys
from pathlib import Path

os.environ["APPLICATION_MODE"] = "TEST"
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_models import RagContextChunk, RetrievedChunk
from rag_service import RagService
from reranker_providers import RerankResult
from storage.vector_store import VectorSearchItem


class _FakeAgentKbRepository:
    def __init__(self, kb_ids):
        self._kb_ids = kb_ids

    def list_kb_ids(self, agent_id):
        return list(self._kb_ids)


class _FakeKbRepository:
    def get_embedding_metadata(self, kb_id):
        return ("vec_chunks", "bge-m3", 3)


class _FakeVectorStore:
    def __init__(self, hits):
        self._hits = hits

    def search(self, kb_id, query_vector, limit):
        return self._hits[:limit]


class _FakeDocumentRepository:
    def __init__(self, rows):
        self._rows = rows

    def fetch_for_search(self, kb_id, chunk_ids):
        wanted = set(chunk_ids)
        return [row for row in self._rows if row.chunk_id in wanted]


class _FakeModelService:
    def __init__(self, reranker_available=False, rerank_scores=None):
        self.embedding_dimension = 3
        self.reranker_available = reranker_available
        self._rerank_scores = rerank_scores or []

    def embed_query(self, query):
        return [0.0, 0.0, 0.0]

    def rerank(self, query, candidates, top_n=None):
        return [
            RerankResult(index=index, score=score, text=candidates[index])
            for index, score in self._rerank_scores
        ]


def _chunk(chunk_id, distance=None, rerank=None):
    return RagContextChunk(
        chunk_id=chunk_id,
        document_id=chunk_id,
        knowledge_base_id=1,
        document_name=f"doc-{chunk_id}.txt",
        chunk_index=chunk_id,
        text=f"text-{chunk_id}",
        vector_distance=distance,
        rerank_score=rerank,
    )


def _build_service(
    hits,
    rows,
    model_service,
    relevance_threshold,
    reranker_enabled=False,
    kb_ids=None,
):
    return RagService(
        model_service=model_service,
        knowledge_base_repository=_FakeKbRepository(),
        document_repository=_FakeDocumentRepository(rows),
        agent_knowledge_base_repository=_FakeAgentKbRepository(
            [1] if kb_ids is None else kb_ids
        ),
        vector_store=_FakeVectorStore(hits),
        final_top_k=5,
        reranker_enabled=reranker_enabled,
        relevance_threshold=relevance_threshold,
    )


def test_relevance_prefers_rerank_score():
    assert _chunk(1, distance=1.0, rerank=0.9).relevance == 0.9


def test_relevance_from_vector_distance():
    assert _chunk(1, distance=0.4).relevance == 0.8
    assert _chunk(1, distance=2.0).relevance == 0.0
    assert _chunk(1, distance=3.0).relevance == 0.0


def test_relevance_none_without_scores():
    assert _chunk(1).relevance is None


def test_vector_path_filters_below_threshold():
    hits = [VectorSearchItem(chunk_id=1, distance=0.2), VectorSearchItem(chunk_id=2, distance=1.8)]
    rows = [
        RetrievedChunk(1, 1, 1, "doc-1.txt", 0, "text-1"),
        RetrievedChunk(2, 2, 1, "doc-2.txt", 1, "text-2"),
    ]
    service = _build_service(hits, rows, _FakeModelService(), relevance_threshold=0.5)

    result = service.retrieve(1, "query")

    assert result.has_knowledge_bases is True
    assert result.below_threshold is False
    assert [chunk.chunk_id for chunk in result.chunks] == [1]


def test_all_chunks_below_threshold():
    hits = [VectorSearchItem(chunk_id=1, distance=1.8), VectorSearchItem(chunk_id=2, distance=1.9)]
    rows = [
        RetrievedChunk(1, 1, 1, "doc-1.txt", 0, "text-1"),
        RetrievedChunk(2, 2, 1, "doc-2.txt", 1, "text-2"),
    ]
    service = _build_service(hits, rows, _FakeModelService(), relevance_threshold=0.5)

    result = service.retrieve(1, "query")

    assert result.chunks == []
    assert result.below_threshold is True


def test_reranker_path_filters_below_threshold():
    hits = [VectorSearchItem(chunk_id=1, distance=0.2), VectorSearchItem(chunk_id=2, distance=0.3)]
    rows = [
        RetrievedChunk(1, 1, 1, "doc-1.txt", 0, "text-1"),
        RetrievedChunk(2, 2, 1, "doc-2.txt", 1, "text-2"),
    ]
    model_service = _FakeModelService(
        reranker_available=True,
        rerank_scores=[(0, 0.95), (1, 0.1)],
    )
    service = _build_service(
        hits,
        rows,
        model_service,
        relevance_threshold=0.5,
        reranker_enabled=True,
    )

    result = service.retrieve(1, "query")

    assert [chunk.chunk_id for chunk in result.chunks] == [1]
    assert result.chunks[0].rerank_score == 0.95


def test_no_knowledge_bases_is_inactive():
    service = _build_service(
        [],
        [],
        _FakeModelService(),
        relevance_threshold=0.5,
        kb_ids=[],
    )

    result = service.retrieve(1, "query")

    assert result.chunks == []
    assert result.has_knowledge_bases is False
    assert result.below_threshold is False
