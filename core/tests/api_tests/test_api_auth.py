"""Тесты авторизации REST API по API-ключу."""

from __future__ import annotations


def test_health_is_public(anon_client):
    response = anon_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_without_key(anon_client):
    response = anon_client.get("/api/models")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_protected_endpoint_with_invalid_key(anon_client):
    response = anon_client.get(
        "/api/models", headers={"Authorization": "Bearer not-a-real-key"}
    )
    assert response.status_code == 401


def test_protected_endpoint_with_non_bearer_scheme(anon_client):
    response = anon_client.get(
        "/api/models", headers={"Authorization": "Basic abc"}
    )
    assert response.status_code == 401


def test_valid_key_allows_access(client):
    response = client.get("/api/models")
    assert response.status_code == 200


def test_revoked_key_is_rejected(app):
    application, use_cases = app
    from fastapi.testclient import TestClient

    created = use_cases.create_api_key.execute("revoked")
    use_cases.delete_api_key.execute(created.id)

    with TestClient(application) as test_client:
        response = test_client.get(
            "/api/models",
            headers={"Authorization": f"Bearer {created.api_key}"},
        )
    assert response.status_code == 401
