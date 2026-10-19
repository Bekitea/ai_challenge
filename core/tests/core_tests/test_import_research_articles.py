"""Импорт научных статей: полный текст, аннотация, дубликаты, лимит."""

import os
import uuid
from pathlib import Path

os.environ["APPLICATION_MODE"] = "TEST"

import pytest

from core.application.dtos.add_documents_result import AddDocumentsResult
from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.dtos.document_status import DOCUMENT_STATUS_READY
from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.use_cases.import_research_articles import (
    ImportResearchArticlesUseCase,
)
from core.domain.entities.research_library import ResearchLibrary
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.orm import Base, KnowledgeBaseORM
from core.infrastructure.persistence.sqlite_document_repository import (
    SqliteDocumentRepository,
)
from core.infrastructure.persistence.sqlite_research_article_repository import (
    SqliteResearchArticleRepository,
)
from core.infrastructure.persistence.sqlite_research_library_repository import (
    SqliteResearchLibraryRepository,
)


class _FakeEnsureLibrary:
    def __init__(self, library: ResearchLibraryDTO):
        self._library = library

    def execute(self, agent_id, library_name=None):
        return self._library


class _FakeSource:
    def __init__(self, candidates: dict[str, ArticleCandidateDTO]):
        self._candidates = candidates

    def get_by_identifier(self, identifier):
        return self._candidates.get(identifier)


class _FakeLocator:
    def __init__(self, urls: dict[str, str]):
        self._urls = urls
        self.calls: list[str | None] = []

    def find_pdf_url(self, doi):
        self.calls.append(doi)
        return self._urls.get(doi or "")


class _FakeDownloader:
    def __init__(self):
        self.calls: list[str] = []

    def download(self, url, destination: Path):
        self.calls.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-1.4 fake")
        return destination


class _FakeExtractor:
    def __init__(self, text="Full text body", error: Exception | None = None):
        self._text = text
        self._error = error

    def extract(self, path):
        if self._error is not None:
            raise self._error
        return self._text


class _FakeAddDocument:
    def __init__(self, document_repository, status=DOCUMENT_STATUS_READY):
        self.calls: list[str] = []
        self._documents = document_repository
        self._status = status

    def execute(self, knowledge_base_id, source_path):
        self.calls.append(source_path)
        document_id = self._documents.create_pending(
            kb_id=knowledge_base_id,
            name=Path(source_path).name,
            source_type="file",
            source_path=source_path,
            content_hash=None,
        )
        self._documents.set_status(
            document_id, self._status, chunk_count=1
        )
        document = self._documents.get(document_id)
        return AddDocumentsResult(documents=[document])


class _FakeDeleteDocument:
    def __init__(self):
        self.calls: list[int] = []

    def execute(self, document_id):
        self.calls.append(document_id)
        return True


def _build_case(candidates, pdf_urls=None, extractor_error=None, batch_limit=5):
    db = DatabaseConnection()
    db.init_tables(Base.metadata)
    library_repo = SqliteResearchLibraryRepository(db.get_session)
    article_repo = SqliteResearchArticleRepository(db.get_session)
    with db.get_session() as session:
        knowledge_base = KnowledgeBaseORM(
            name=f"kb-{uuid.uuid4().hex[:8]}",
            embedding_model="test",
            embedding_dimension=1024,
        )
        session.add(knowledge_base)
        session.commit()
        kb_id = knowledge_base.id
    library = library_repo.create(
        ResearchLibrary(
            id=None,
            name=f"Import-{uuid.uuid4().hex[:8]}",
            knowledge_base_id=kb_id,
        )
    )
    library_dto = ResearchLibraryDTO(
        id=library.id, name=library.name, knowledge_base_id=library.knowledge_base_id
    )
    document_repository = SqliteDocumentRepository(db.get_session, object())
    fakes = {
        "downloader": _FakeDownloader(),
        "extractor": _FakeExtractor(error=extractor_error),
        "add_document": _FakeAddDocument(document_repository),
        "delete_document": _FakeDeleteDocument(),
        "locator": _FakeLocator(pdf_urls or {}),
    }
    case = ImportResearchArticlesUseCase(
        ensure_library=_FakeEnsureLibrary(library_dto),
        article_repository=article_repo,
        source=_FakeSource(candidates),
        pdf_locator=fakes["locator"],
        downloader=fakes["downloader"],
        text_extractor=fakes["extractor"],
        add_document=fakes["add_document"],
        delete_document=fakes["delete_document"],
        data_dir=str(Path(os.environ.get("AI_CHAT_TEST_DATA_DIR", "./test-data")) / "research"),
        batch_limit=batch_limit,
    )
    return case, article_repo, fakes, db


def _candidate(doi, abstract="Abstract"):
    return ArticleCandidateDTO(
        title=f"Title {doi}",
        doi=doi,
        abstract=abstract,
        is_open_access=True,
        pdf_url="https://example.org/paper.pdf",
    )


def test_import_indexes_full_text():
    case, articles, fakes, db = _build_case({"10.1/a": _candidate("10.1/a")})

    result = case.execute(1, ["10.1/a"])

    assert result.results[0].ok is True
    assert result.results[0].status == "indexed"
    assert result.results[0].document_id == 1
    assert fakes["downloader"].calls == ["https://example.org/paper.pdf"]
    article = articles.get_by_identifier(result.library.id, "10.1/a")
    assert article.status == "indexed"
    assert article.document_id == 1
    db.close()


def test_import_falls_back_to_abstract_when_pdf_fails():
    case, _articles, _fakes, db = _build_case(
        {"10.1/b": _candidate("10.1/b")},
        extractor_error=RuntimeError("scan"),
    )

    result = case.execute(1, ["10.1/b"])

    assert result.results[0].ok is True
    assert result.results[0].status == "abstract_only"
    db.close()


def test_import_without_abstract_or_pdf_marks_error():
    candidate = _candidate("10.1/c", abstract=None)
    candidate.pdf_url = None
    case, _articles, _fakes, db = _build_case({"10.1/c": candidate})

    result = case.execute(1, ["10.1/c"])

    assert result.results[0].ok is False
    assert result.results[0].status == "error"
    db.close()


def test_import_is_idempotent_and_force_reindexes():
    case, _articles, fakes, db = _build_case({"10.1/d": _candidate("10.1/d")})

    first = case.execute(1, ["10.1/d"])
    assert first.results[0].status == "indexed"
    assert len(fakes["add_document"].calls) == 1

    second = case.execute(1, ["10.1/d"])
    assert second.results[0].status == "indexed"
    assert len(fakes["add_document"].calls) == 1
    assert "уже в библиотеке" in (second.results[0].detail or "")

    third = case.execute(1, ["10.1/d"], force=True)
    assert third.results[0].status == "indexed"
    assert len(fakes["add_document"].calls) == 2
    assert len(fakes["delete_document"].calls) == 1
    db.close()


def test_import_respects_batch_limit_and_missing_articles():
    case, _articles, _fakes, db = _build_case({"10.1/e": _candidate("10.1/e")}, batch_limit=1)

    with pytest.raises(ValueError):
        case.execute(1, ["10.1/e", "10.1/unknown"])

    result = case.execute(1, ["10.1/unknown"])
    assert result.results[0].ok is False
    assert result.results[0].status == "error"
    db.close()
