"""Репозиторий статей научной библиотеки: дедупликация и изоляция по library_id."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.domain.entities.research_library import ResearchLibrary
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.orm import Base
from core.infrastructure.persistence.sqlite_research_article_repository import (
    SqliteResearchArticleRepository,
)
from core.infrastructure.persistence.sqlite_research_library_repository import (
    SqliteResearchLibraryRepository,
)


def _repositories():
    db = DatabaseConnection()
    db.init_tables(Base.metadata)
    return (
        db,
        SqliteResearchLibraryRepository(db.get_session),
        SqliteResearchArticleRepository(db.get_session),
    )


def _candidate(doi: str, title: str) -> ArticleCandidateDTO:
    return ArticleCandidateDTO(
        title=title,
        doi=doi,
        openalex_id="https://openalex.org/W123",
        authors=["A. Author"],
        publication_year=2023,
        abstract="Abstract text",
        cited_by_count=5,
        is_open_access=True,
    )


def _library_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_upsert_deduplicates_by_normalized_doi():
    db, libraries, articles = _repositories()
    library = libraries.create(ResearchLibrary(id=None, name=_library_name("Dedup")))

    first = articles.upsert(library.id, _candidate("10.1000/ABC", "Title 1"), "candidate")
    second = articles.upsert(
        library.id,
        _candidate("https://doi.org/10.1000/abc", "Title 2"),
        "indexed",
    )

    assert first.id == second.id
    assert articles.count(library.id) == 1
    assert second.status == "indexed"
    assert second.doi == "10.1000/abc"
    db.close()


def test_same_doi_lives_independently_in_two_libraries():
    db, libraries, articles = _repositories()
    library_a = libraries.create(ResearchLibrary(id=None, name=_library_name("LibA")))
    library_b = libraries.create(ResearchLibrary(id=None, name=_library_name("LibB")))

    article_a = articles.upsert(library_a.id, _candidate("10.1/x", "A"), "indexed")
    article_b = articles.upsert(library_b.id, _candidate("10.1/x", "B"), "abstract_only")

    assert article_a.id != article_b.id
    assert articles.count(library_a.id) == 1
    assert articles.count(library_b.id) == 1
    assert articles.list(library_a.id)[0].title == "A"
    assert articles.list(library_b.id)[0].title == "B"
    db.close()


def test_get_by_name_is_case_insensitive_for_cyrillic():
    db, libraries, _articles = _repositories()
    library = libraries.create(
        ResearchLibrary(id=None, name=_library_name("Библиотека"))
    )

    assert libraries.get_by_name(library.name.upper()).id == library.id
    assert libraries.get_by_name("не существует") is None
    db.close()
