"""REST API научных библиотек: создание, переключение, открепление, удаление."""

from __future__ import annotations

import uuid

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.orm import Base
from core.infrastructure.persistence.sqlite_research_article_repository import (
    SqliteResearchArticleRepository,
)

_CHAT_SETTINGS = {"provider": "yandex", "model_id": "aliceai-llm-flash/latest"}


def _create_chat(client, name: str = "research api") -> int:
    response = client.post(
        "/api/chats", json={"name": name, "settings": _CHAT_SETTINGS}
    )
    assert response.status_code == 201
    return response.json()["agent_id"]


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_library(client, chat_id: int, name: str):
    response = client.post(
        f"/api/chats/{chat_id}/library/create",
        json={
            "name": name,
            "goal": "Проверить гипотезу",
            "field": "machine learning",
            "keywords": ["RAG"],
            "year_from": 2020,
            "year_to": 2026,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get_active_library(client):
    chat_id = _create_chat(client)
    name = _name("API Library")

    library = _create_library(client, chat_id, name)

    assert library["name"] == name
    assert library["knowledge_base_id"] is not None
    assert library["goal"] == "Проверить гипотезу"

    active = client.get(f"/api/chats/{chat_id}/library")
    assert active.status_code == 200
    assert active.json()["id"] == library["id"]

    available = client.get(f"/api/chats/{chat_id}/library/available")
    assert available.status_code == 200
    assert any(item["id"] == library["id"] for item in available.json())


def test_switch_library_reuses_it_in_another_chat(client):
    first_chat = _create_chat(client, "first")
    second_chat = _create_chat(client, "second")
    library = _create_library(client, first_chat, _name("Shared"))

    response = client.post(
        f"/api/chats/{second_chat}/library/switch",
        json={"name": library["name"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["library"]["id"] == library["id"]
    assert body["knowledge_base_attached"] is True
    assert body["previous_library_detached"] is False

    active = client.get(f"/api/chats/{second_chat}/library")
    assert active.json()["id"] == library["id"]


def test_detach_library_keeps_it_available(client):
    chat_id = _create_chat(client)
    library = _create_library(client, chat_id, _name("Detach"))

    response = client.delete(f"/api/chats/{chat_id}/library")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert client.get(f"/api/chats/{chat_id}/library").json() is None

    available = client.get(f"/api/chats/{chat_id}/library/available").json()
    assert any(item["id"] == library["id"] for item in available)


def test_delete_library_requires_confirm_name(client):
    chat_id = _create_chat(client)
    library = _create_library(client, chat_id, _name("Delete"))
    url = f"/api/libraries/{library['id']}"

    wrong = client.delete(url, params={"confirm_name": "wrong"})
    assert wrong.status_code == 400

    deleted = client.delete(url, params={"confirm_name": library["name"]})
    assert deleted.status_code == 200
    assert deleted.json()["deleted_articles"] == 0

    available = client.get(f"/api/chats/{chat_id}/library/available").json()
    assert all(item["id"] != library["id"] for item in available)


def test_unknown_chat_returns_404(client):
    response = client.get("/api/chats/999999/library")
    assert response.status_code == 404


def _insert_article(library_id: int, doi: str, year: int, status: str) -> None:
    db = DatabaseConnection()
    db.init_tables(Base.metadata)
    repository = SqliteResearchArticleRepository(db.get_session)
    repository.upsert(
        library_id,
        ArticleCandidateDTO(
            title=f"Glaucoma paper {doi}",
            doi=doi,
            authors=["A. Author"],
            publication_year=year,
            abstract="OCT screening",
        ),
        status,
    )
    db.close()


def test_list_articles_by_chat_and_library(client):
    chat_id = _create_chat(client)
    library = _create_library(client, chat_id, _name("Articles"))
    _insert_article(library["id"], "10.9/a", 2024, "indexed")
    _insert_article(library["id"], "10.9/b", 2023, "abstract_only")

    by_chat = client.get(f"/api/chats/{chat_id}/library/articles")
    assert by_chat.status_code == 200, by_chat.text
    page = by_chat.json()
    assert page["total"] == 2
    assert len(page["articles"]) == 2
    assert page["library"]["id"] == library["id"]

    by_library = client.get(f"/api/libraries/{library['id']}/articles")
    assert by_library.status_code == 200
    assert by_library.json()["total"] == 2

    filtered = client.get(
        f"/api/libraries/{library['id']}/articles",
        params={"status": "indexed"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["articles"][0]["doi"] == "10.9/a"


def test_list_articles_empty_and_not_found(client):
    chat_id = _create_chat(client)

    no_library = client.get(f"/api/chats/{chat_id}/library/articles")
    assert no_library.status_code == 404

    unknown = client.get("/api/libraries/999999/articles")
    assert unknown.status_code == 404
