"""Привязка/открепление/удаление научных библиотек и наследование веткой."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

import pytest

from core.application.dtos.settings_dto import SettingsDTO
from core.application.dtos.strategy_selection import StrategySelection
from core.di.app_factory import initialize_application


def _chat(bundle, name: str):
    return bundle.create_chat.execute(
        name, None, SettingsDTO(), StrategySelection("DefaultStrategy")
    )


def _library_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _attached_kb_ids(bundle, agent_id: int) -> set[int]:
    return {
        kb.id for kb in bundle.list_agent_knowledge_bases.execute(agent_id)
    }


def test_create_library_attaches_its_knowledge_base():
    bundle = initialize_application()
    chat = _chat(bundle, "Research bind chat")

    library = bundle.research_create_library.execute(
        chat.agent_id, _library_name("Bind")
    )

    assert library.knowledge_base_id is not None
    assert library.knowledge_base_id in _attached_kb_ids(bundle, chat.agent_id)


def test_switch_detaches_previous_library_kb_but_keeps_manual_kb():
    bundle = initialize_application()
    chat = _chat(bundle, "Research switch chat")
    first = bundle.research_create_library.execute(
        chat.agent_id, _library_name("First")
    )
    manual = bundle.create_knowledge_base.execute(_library_name("Manual"))
    bundle.attach_knowledge_base.execute(chat.agent_id, manual.id)

    second = bundle.research_create_library.execute(
        chat.agent_id, _library_name("Second")
    )

    attached = _attached_kb_ids(bundle, chat.agent_id)
    assert first.knowledge_base_id not in attached
    assert second.knowledge_base_id in attached
    assert manual.id in attached


def test_detach_keeps_library_and_removes_binding_and_kb():
    bundle = initialize_application()
    chat = _chat(bundle, "Research detach chat")
    library = bundle.research_create_library.execute(
        chat.agent_id, _library_name("Detach")
    )

    result = bundle.research_detach_library.execute(chat.agent_id)

    assert result.success is True
    assert bundle.research_get_active_library.execute(chat.agent_id) is None
    assert library.knowledge_base_id not in _attached_kb_ids(bundle, chat.agent_id)
    assert any(
        item.id == library.id
        for item in bundle.research_list_libraries.execute()
    )


def test_delete_requires_confirmation_and_removes_library_and_kb():
    bundle = initialize_application()
    chat = _chat(bundle, "Research delete chat")
    library = bundle.research_create_library.execute(
        chat.agent_id, _library_name("Delete")
    )
    kb_id = library.knowledge_base_id

    with pytest.raises(ValueError):
        bundle.research_delete_library.execute(library.name, "wrong")

    result = bundle.research_delete_library.execute(
        library.name, library.name
    )

    assert result.success is True
    assert result.affected_chats == 1
    assert bundle.research_get_active_library.execute(chat.agent_id) is None
    assert all(
        item.id != library.id
        for item in bundle.research_list_libraries.execute()
    )
    assert all(kb.id != kb_id for kb in bundle.list_knowledge_bases.execute())


def test_branch_inherits_research_library_and_kb():
    bundle = initialize_application()
    parent = _chat(bundle, "Research parent chat")
    library = bundle.research_create_library.execute(
        parent.agent_id, _library_name("Branch")
    )

    branch = bundle.create_branch.execute(parent.agent_id, "Research branch")

    branch_library = bundle.research_get_active_library.execute(branch.agent_id)
    assert branch_library is not None
    assert branch_library.id == library.id
    assert library.knowledge_base_id in _attached_kb_ids(
        bundle, branch.agent_id
    )
