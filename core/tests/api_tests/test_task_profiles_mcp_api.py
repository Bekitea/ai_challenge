"""REST API: MCP-серверы профиля задачи и автоподключение при создании чата."""

from __future__ import annotations

import uuid

_CHAT_SETTINGS = {"provider": "yandex", "model_id": "aliceai-llm-flash/latest"}


def _create_profile(client, name: str, servers: list[str]) -> dict:
    response = client.post(
        "/api/task-profiles",
        json={
            "name": name,
            "description": "Profile with MCP",
            "mcp_servers": servers,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_profile_with_mcp_servers(client):
    name = f"API MCP-{uuid.uuid4().hex[:8]}"
    profile = _create_profile(client, name, ["time"])

    assert profile["mcp_servers"] == ["time"]

    detail = client.get(f"/api/task-profiles/{profile['id']}")
    assert detail.status_code == 200
    assert detail.json()["mcp_servers"] == ["time"]


def test_update_profile_mcp_servers(client):
    name = f"API Edit-{uuid.uuid4().hex[:8]}"
    profile = _create_profile(client, name, [])

    response = client.put(
        f"/api/task-profiles/{profile['id']}/mcp-servers",
        json={"servers": ["time"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["mcp_servers"] == ["time"]


def test_chat_created_with_profile_connects_its_mcp(client):
    name = f"API Chat Profile-{uuid.uuid4().hex[:8]}"
    profile = _create_profile(client, name, ["time"])

    created = client.post(
        "/api/chats",
        json={
            "name": "Profile MCP chat",
            "settings": _CHAT_SETTINGS,
            "task_profile_id": profile["id"],
        },
    )
    assert created.status_code == 201, created.text
    chat = created.json()
    assert any("MCP 'Time'" in message for message in chat["mcp_messages"])

    mcp = client.get(f"/api/chats/{chat['agent_id']}/mcp")
    assert mcp.status_code == 200
    time_server = next(s for s in mcp.json() if s["name"] == "time")
    assert time_server["connected"] is True
