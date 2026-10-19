"""Изоляция научных библиотек: у каждого чата своя библиотека и БЗ."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

from core.application.dtos.settings_dto import SettingsDTO
from core.application.dtos.strategy_selection import StrategySelection
from core.di.app_factory import initialize_application


def _chat(bundle, name: str):
    return bundle.create_chat.execute(
        name, None, SettingsDTO(), StrategySelection("DefaultStrategy")
    )


def test_two_chats_get_separate_libraries():
    bundle = initialize_application()
    chat_a = _chat(bundle, "Deep Learning chat")
    chat_b = _chat(bundle, "Medical NLP chat")

    library_a = bundle.research_ensure_library.execute(chat_a.agent_id)
    library_b = bundle.research_ensure_library.execute(chat_b.agent_id)

    assert library_a.id != library_b.id
    assert library_a.knowledge_base_id != library_b.knowledge_base_id
    assert chat_a.name in library_a.name
    assert chat_b.name in library_b.name

    again = bundle.research_ensure_library.execute(chat_a.agent_id)
    assert again.id == library_a.id

    libraries = bundle.research_list_libraries.execute()
    library_ids = {library.id for library in libraries}
    assert {library_a.id, library_b.id}.issubset(library_ids)


def test_switch_library_changes_active_library():
    bundle = initialize_application()
    chat_a = _chat(bundle, "Chat A")
    chat_b = _chat(bundle, "Chat B")
    library_a = bundle.research_ensure_library.execute(chat_a.agent_id)
    library_b = bundle.research_ensure_library.execute(chat_b.agent_id)

    switched = bundle.research_switch_library.execute(
        chat_a.agent_id, library_b.name
    )
    assert switched.id == library_b.id
    assert bundle.research_ensure_library.execute(chat_a.agent_id).id == library_b.id
    assert bundle.research_ensure_library.execute(chat_b.agent_id).id == library_b.id

    back = bundle.research_switch_library.execute(chat_a.agent_id, library_a.name)
    assert back.id == library_a.id


def test_create_and_update_library_profile():
    bundle = initialize_application()
    chat = _chat(bundle, "Profile chat")

    library_name = f"Квантовые вычисления-{uuid.uuid4().hex[:8]}"
    library = bundle.research_create_library.execute(
        chat.agent_id,
        library_name,
        goal="Оценить применимость VQE",
        field="quantum computing",
        keywords=["VQE", "NISQ"],
        year_from=2019,
        year_to=2026,
        language="en",
    )
    assert library.name == library_name
    assert library.goal == "Оценить применимость VQE"

    updated = bundle.research_update_profile.execute(
        chat.agent_id,
        goal="Новая цель диссертации",
        keywords=["VQE", "error mitigation"],
        year_from=2020,
    )
    assert updated.goal == "Новая цель диссертации"
    assert updated.keywords == ["VQE", "error mitigation"]
    assert updated.year_from == 2020
    assert updated.year_to == 2026
    assert updated.field == "quantum computing"
