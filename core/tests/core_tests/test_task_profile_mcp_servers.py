"""MCP-серверы профиля задачи, предустановленный профиль и автоподключение."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

import pytest

from core.application.dtos.settings_dto import SettingsDTO
from core.application.dtos.strategy_selection import StrategySelection
from core.di.app_factory import initialize_application


def _chat(bundle, name: str, profile_id: str | None = None):
    return bundle.create_chat.execute(
        name,
        None,
        SettingsDTO(),
        StrategySelection("DefaultStrategy"),
        task_profile_id=profile_id,
    )


def test_preset_research_assistant_is_created_once():
    bundle = initialize_application()

    first = bundle.ensure_preset_task_profiles.execute()
    second = bundle.ensure_preset_task_profiles.execute()

    assert first.created == 1
    assert first.names == ["Научный ассистент"]
    assert second.created == 0
    assert second.skipped == 1

    profile = next(
        p
        for p in bundle.list_task_profiles.execute()
        if p.name == "Научный ассистент"
    )
    assert profile.mcp_servers == ["research", "openalex", "time"]
    assert profile.invariants_count == 5
    assert "Научный ассистент" in profile.description


def test_create_and_update_profile_mcp_servers():
    bundle = initialize_application()
    name = f"Profile-{uuid.uuid4().hex[:8]}"

    created = bundle.create_task_profile.execute(
        name,
        "Description",
        "Preferences",
        ["Rule"],
        ["time"],
    )
    assert created.mcp_servers == ["time"]

    updated = bundle.set_task_profile_mcp_servers.execute(
        created.id, ["time", "research"]
    )
    assert updated.mcp_servers == ["time", "research"]

    detail = bundle.get_task_profile_memory.execute(created.id)
    assert detail.mcp_servers == ["time", "research"]


def test_unknown_mcp_server_is_rejected():
    bundle = initialize_application()

    with pytest.raises(ValueError):
        bundle.create_task_profile.execute(
            f"Bad-{uuid.uuid4().hex[:8]}",
            "Description",
            mcp_servers=["does-not-exist"],
        )


def test_chat_connects_profile_mcp_servers_on_creation():
    bundle = initialize_application()
    profile = bundle.create_task_profile.execute(
        f"Time-{uuid.uuid4().hex[:8]}",
        "Profile with time MCP",
        mcp_servers=["time"],
    )
    chat = _chat(bundle, "Profile MCP chat", profile.id)

    connected = bundle.list_connected_mcp.execute(chat.agent_id)
    assert any(server.name == "time" and server.connected for server in connected)
    assert any("MCP 'Time'" in message for message in chat.mcp_messages)
