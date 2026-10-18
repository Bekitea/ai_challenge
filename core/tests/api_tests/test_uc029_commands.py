"""REST API-тесты ассистентских команд (/help, /support, /files)."""

from __future__ import annotations

import pytest

import config

_CHAT_SETTINGS = {"provider": "yandex", "model_id": "aliceai-llm-flash/latest"}


@pytest.fixture(autouse=True)
def _enable_assistant_commands(monkeypatch):
    """Включает замороженные команды для тестов их логики (BACKLOG.md, раздел 2)."""
    monkeypatch.setattr(config, "ASSISTANT_COMMANDS_ENABLED", True)


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


def test_files_command_connects_files_and_git_mcp(client):
    """UC-030: /files отвечает и подключает files + git MCP."""
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands",
        json={"command": "/files найди использования McpGateway"},
    )
    assert response.status_code == 200
    assert response.json()["response"] is not None
    assert response.json()["response"]["content"]

    mcp = client.get(f"/api/chats/{chat_id}/mcp")
    connected = {s["name"] for s in mcp.json() if s["connected"]}
    assert "files" in connected
    assert "git" in connected


def test_bare_files_returns_hint_without_agent_call(client):
    """Голый /files возвращает подсказку и не зовёт агента."""
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands", json={"command": "/files"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] is None
    assert any("Задайте задачу по файлам проекта" in m for m in body["messages"])


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


def test_frozen_assistant_command_returns_400(client, monkeypatch):
    """Замороженная команда возвращает 400 и не подключает MCP."""
    monkeypatch.setattr(config, "ASSISTANT_COMMANDS_ENABLED", False)
    chat_id = _create_chat(client)

    response = client.post(
        f"/api/chats/{chat_id}/commands",
        json={"command": "/files найди McpGateway"},
    )
    assert response.status_code == 400
    assert "отключена" in response.json()["detail"]

    mcp = client.get(f"/api/chats/{chat_id}/mcp")
    connected = {s["name"] for s in mcp.json() if s["connected"]}
    assert "files" not in connected
    assert "git" not in connected
