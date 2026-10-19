"""REST API-тесты эндпоинта AI-ревью PR (UC-032, ``POST /api/review-pr``)."""

from __future__ import annotations

import config

_PAYLOAD = {
    "repo": "Bekitea/ai_challenge",
    "pr_number": 42,
    "pr_title": "Добавить эндпоинт ревью",
    "author": "dev",
    "base_branch": "main",
    "head_branch": "feature/review",
    "changed_files": ["core/application/use_cases/review_pull_request.py"],
    "diff": (
        "diff --git a/core/x.py b/core/x.py\n"
        "--- a/core/x.py\n"
        "+++ b/core/x.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    ),
}


def test_review_pr_returns_markdown(client):
    """POST /api/review-pr возвращает текст ревью и список RAG-источников."""
    response = client.post("/api/review-pr", json=_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["review"], str)
    assert body["review"].strip()
    assert body["rag_sources"] == []


def test_review_pr_empty_diff_is_rejected(client):
    """Пустой diff отклоняется валидацией схемы (422)."""
    payload = {**_PAYLOAD, "diff": ""}

    response = client.post("/api/review-pr", json=payload)

    assert response.status_code == 422


def test_review_pr_requires_api_key(anon_client):
    """Без Authorization-заголовка эндпоинт недоступен (401)."""
    response = anon_client.post("/api/review-pr", json=_PAYLOAD)

    assert response.status_code == 401


def test_review_pr_disabled_returns_400(client, monkeypatch):
    """При REVIEW_ENABLED=false эндпоинт сообщает об отключении (400)."""
    monkeypatch.setattr(config, "REVIEW_ENABLED", False)

    response = client.post("/api/review-pr", json=_PAYLOAD)

    assert response.status_code == 400
    assert "отключено" in response.json()["detail"]
