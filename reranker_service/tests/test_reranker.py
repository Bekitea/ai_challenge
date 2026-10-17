"""Тесты HTTP-контракта reranker_service (TEI-совместимый ``POST /rerank``)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client(server) -> TestClient:
    return TestClient(server.app)


def test_health_loading_when_model_not_loaded(server):
    """Пока модель не загружена, /health сообщает loading."""
    response = _client(server).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "loading"


def test_health_ok_when_model_loaded(server, fake_encoder):
    """С загруженной моделью /health сообщает ok."""
    response = _client(server).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rerank_sorts_by_score_desc(server, fake_encoder):
    """Результаты отсортированы по score по убыванию."""
    fake_encoder.predictions = [0.1, 0.9, 0.5]

    response = _client(server).post(
        "/rerank", json={"query": "q", "texts": ["a", "b", "c"]}
    )

    assert response.status_code == 200
    assert [item["index"] for item in response.json()] == [1, 2, 0]


def test_rerank_respects_top_n(server, fake_encoder):
    """top_n ограничивает число возвращаемых результатов."""
    fake_encoder.predictions = [0.1, 0.9, 0.5]

    response = _client(server).post(
        "/rerank", json={"query": "q", "texts": ["a", "b", "c"], "top_n": 2}
    )

    assert response.status_code == 200
    assert [item["index"] for item in response.json()] == [1, 2]


def test_rerank_return_text(server, fake_encoder):
    """return_text возвращает исходный текст для каждого результата."""
    fake_encoder.predictions = [0.2, 0.8]

    response = _client(server).post(
        "/rerank",
        json={"query": "q", "texts": ["low", "high"], "return_text": True},
    )

    body = response.json()
    assert body[0]["index"] == 1
    assert body[0]["text"] == "high"


def test_rerank_empty_texts_returns_empty(server, fake_encoder):
    """Пустой список текстов — пустой ответ без обращения к модели."""
    response = _client(server).post("/rerank", json={"query": "q", "texts": []})

    assert response.status_code == 200
    assert response.json() == []


def test_rerank_blank_query_returns_400(server, fake_encoder):
    """Пустой query — 400."""
    response = _client(server).post(
        "/rerank", json={"query": "   ", "texts": ["a"]}
    )

    assert response.status_code == 400


def test_rerank_model_not_loaded_returns_503(server):
    """Без загруженной модели /rerank отвечает 503 (fail fast)."""
    response = _client(server).post(
        "/rerank", json={"query": "q", "texts": ["a"]}
    )

    assert response.status_code == 503
