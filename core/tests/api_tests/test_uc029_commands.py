"""REST API-тесты ассистентских команд (/help, /support)."""

from __future__ import annotations

_CHAT_SETTINGS = {"provider": "yandex", "model_id": "aliceai-llm-flash/latest"}


def _create_chat(client, name: str = "support test") -> int:
    response = client.post(
        "/api/chats",
        json={"name": name, "settings": _CHAT_SETTINGS},
    )
    assert response.status_code == 201
    return response.json()["agent_id"]


def test_support_command_answers_and_connects_mcp(client):
    """UC-029: /support отвечает и подключает MCP-сервер support."""
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands",
        json={"command": "/support T-1001 почему не работает авторизация?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] is not None
    assert body["response"]["content"]
    assert isinstance(body["messages"], list)

    mcp = client.get(f"/api/chats/{chat_id}/mcp")
    assert mcp.status_code == 200
    support = next(s for s in mcp.json() if s["name"] == "support")
    assert support["connected"] is True


def test_bare_support_returns_hint_without_agent_call(client):
    """Голый /support возвращает подсказку и не зовёт агента."""
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands", json={"command": "/support"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] is None
    assert any("Задайте вопрос поддержки" in m for m in body["messages"])


def test_help_command_connects_git_mcp(client):
    """UC-027: /help отвечает и подключает git MCP."""
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands",
        json={"command": "/help как устроен проект?"},
    )
    assert response.status_code == 200
    assert response.json()["response"] is not None

    mcp = client.get(f"/api/chats/{chat_id}/mcp")
    git = next(s for s in mcp.json() if s["name"] == "git")
    assert git["connected"] is True


def test_unknown_command_returns_400(client):
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands", json={"command": "/nope"}
    )
    assert response.status_code == 400


def test_command_missing_chat_returns_404(client):
    response = client.post(
        "/api/chats/999999/commands", json={"command": "/support привет"}
    )
    assert response.status_code == 404
