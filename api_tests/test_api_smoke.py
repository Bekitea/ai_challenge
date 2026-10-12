"""Базовые тесты REST API (in-process, MockLlmProvider)."""

from __future__ import annotations

_CHAT_SETTINGS = {"provider": "yandex", "model_id": "aliceai-llm-flash/latest"}


def _create_chat(client, name: str = "web test") -> int:
    response = client.post(
        "/api/chats",
        json={"name": name, "settings": _CHAT_SETTINGS},
    )
    assert response.status_code == 201
    return response.json()["agent_id"]


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_models(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_chat_and_send_message(client):
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/messages", json={"message": "Привет"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["content"]

    history = client.get(f"/api/chats/{chat_id}/history")
    assert history.status_code == 200
    roles = [m["role"] for m in history.json()]
    assert "user" in roles
    assert "assistant" in roles


def test_get_update_settings(client):
    chat_id = _create_chat(client)

    response = client.get(f"/api/chats/{chat_id}/settings")
    assert response.status_code == 200

    updated = dict(response.json())
    updated["temperature"] = 0.5
    put = client.put(f"/api/chats/{chat_id}/settings", json=updated)
    assert put.status_code == 200
    assert put.json()["temperature"] == 0.5


def test_change_phase(client):
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/phase", json={"command": "/execute"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["current_phase"] == "EXECUTE"


def test_get_chat_not_found(client):
    response = client.get("/api/chats/999999")
    assert response.status_code == 404


def test_chat_info(client):
    chat_id = _create_chat(client)
    response = client.get(f"/api/chats/{chat_id}/info")
    assert response.status_code == 200
    assert response.json()["agent_id"] == chat_id
