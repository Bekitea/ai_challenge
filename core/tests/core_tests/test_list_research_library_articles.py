"""Список статей библиотеки: фильтры, total и пагинация."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

import pytest

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.use_cases.list_research_library_articles import (
    ListResearchLibraryArticlesUseCase,
)
from core.domain.entities.research_library import ResearchLibrary
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.orm import Base
from core.infrastructure.persistence.sqlite_research_article_repository import (
    SqliteResearchArticleRepository,
)
from core.infrastructure.persistence.sqlite_research_library_repository import (
    SqliteResearchLibraryRepository,
)


def _setup():
    db = DatabaseConnection()
    db.init_tables(Base.metadata)
    libraries = SqliteResearchLibraryRepository(db.get_session)
    articles = SqliteResearchArticleRepository(db.get_session)
    library = libraries.create(
        ResearchLibrary(id=None, name=f"List-{uuid.uuid4().hex[:8]}")
    )
    for doi, year, status in (
        ("10.1/a", 2024, "indexed"),
        ("10.1/b", 2023, "abstract_only"),
        ("10.1/c", 2022, "indexed"),
    ):
        articles.upsert(
            library.id,
            ArticleCandidateDTO(
                title=f"Glaucoma study {doi}",
                doi=doi,
                authors=["Alice", "Bob"],
                publication_year=year,
                abstract="OCT and deep learning",
            ),
            status,
        )
    use_case = ListResearchLibraryArticlesUseCase(libraries, articles)
    return db, use_case, library


def test_list_articles_returns_total_and_filters():
    db, use_case, library = _setup()

    page = use_case.execute(library.id, limit=2)
    assert page.total == 3
    assert len(page.articles) == 2
    assert page.limit == 2

    filtered = use_case.execute(library.id, status="indexed")
    assert filtered.total == 2
    assert all(a.status == "indexed" for a in filtered.articles)

    by_year = use_case.execute(library.id, year_from=2023, year_to=2024)
    assert by_year.total == 2

    by_query = use_case.execute(library.id, query="glaucoma study 10.1/b")
    assert by_query.total == 1
    assert by_query.articles[0].doi == "10.1/b"
    db.close()


def test_list_articles_unknown_library_raises():
    db, use_case, _library = _setup()
    with pytest.raises(ValueError):
        use_case.execute(999999)
    db.close()
