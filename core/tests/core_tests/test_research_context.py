"""Контекст обзора, RAG-рекомендации и суммаризация research-библиотеки."""

import os
import uuid

os.environ["APPLICATION_MODE"] = "TEST"

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.application.use_cases.build_review_context import (
    BuildReviewContextUseCase,
)
from core.application.use_cases.recommend_research_articles import (
    RecommendResearchArticlesUseCase,
)
from core.application.use_cases.search_research_library import (
    SearchResearchLibraryUseCase,
)
from core.application.use_cases.summarize_research_articles import (
    SummarizeResearchArticlesUseCase,
)
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.dtos.rag_retrieval_result import RagRetrievalResult
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


class _FakeRag:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve_from_knowledge_base(self, kb_id, query, top_k=None, **kwargs):
        return RagRetrievalResult(chunks=self._chunks, has_knowledge_bases=True)


class _FakeProvider:
    provider_name = "fake"

    def __init__(self, content="Сводка статьи"):
        self.content = content
        self.calls = 0

    def generate(self, messages, **kwargs):
        self.calls += 1
        return LlmResponse(content=self.content)


class _FakeRegistry:
    def __init__(self, provider):
        self._provider = provider

    def get(self, name):
        return self._provider if name == self._provider.provider_name else None

    def all(self):
        return {self._provider.provider_name: self._provider}


def _setup():
    db = DatabaseConnection()
    db.init_tables(Base.metadata)
    libraries = SqliteResearchLibraryRepository(db.get_session)
    articles = SqliteResearchArticleRepository(db.get_session)
    with db.get_session() as session:
        knowledge_base = KnowledgeBaseORM(
            name=f"context-kb-{uuid.uuid4().hex[:8]}",
            embedding_model="test",
            embedding_dimension=1024,
        )
        session.add(knowledge_base)
        session.commit()
        kb_id = knowledge_base.id
    library = libraries.create(
        ResearchLibrary(
            id=None,
            name=f"Context-{uuid.uuid4().hex[:8]}",
            knowledge_base_id=kb_id,
            year_from=2020,
            year_to=2025,
        )
    )
    library_dto = ResearchLibraryDTO(
        id=library.id,
        name=library.name,
        knowledge_base_id=library.knowledge_base_id,
        year_from=library.year_from,
        year_to=library.year_to,
    )
    return db, articles, library_dto


def _article(articles, library_id, doi, year, abstract):
    return articles.upsert(
        library_id,
        ArticleCandidateDTO(
            title=f"Title {doi}",
            doi=doi,
            authors=["Alice", "Bob", "Carol", "Dave"],
            publication_year=year,
            abstract=abstract,
        ),
        "abstract_only",
    )


def test_review_context_uses_summaries_and_respects_budget():
    db, articles, library = _setup()
    first = _article(articles, library.id, "10.2/a", 2024, "Abstract A")
    second = _article(articles, library.id, "10.2/b", 2022, "Abstract B")
    articles.set_summary(first.id, "Summary A", "fake")
    articles.set_summary(second.id, "Summary B", "fake")

    use_case = BuildReviewContextUseCase(_FakeEnsureLibrary(library), articles)
    context = use_case.execute(1, max_chars=100000)

    assert context.total_matched == 2
    assert context.returned == 2
    assert context.truncated is False
    assert context.articles[0].has_summary is True
    assert context.articles[0].content in {"Summary A", "Summary B"}
    assert "et al." in context.articles[0].citation

    small = use_case.execute(1, max_chars=20, limit=10)
    assert small.truncated is True
    db.close()


def test_search_library_maps_chunks_to_articles():
    db, articles, library = _setup()
    article = _article(articles, library.id, "10.2/c", 2023, "Abstract C")
    chunk = RagContextChunk(
        chunk_id=10,
        document_id=55,
        knowledge_base_id=1,
        document_name="doc",
        chunk_index=0,
        text="relevant text",
        rerank_score=0.9,
    )

    class _ArticlesWithDocument:
        def __init__(self, repo, document_id, article):
            self._repo = repo
            self._document_id = document_id
            self._article = article

        def get_by_document(self, library_id, document_id):
            if document_id == self._document_id:
                return self._article
            return self._repo.get_by_document(library_id, document_id)

    repo = _ArticlesWithDocument(articles, 55, article)
    use_case = SearchResearchLibraryUseCase(
        _FakeEnsureLibrary(library), repo, _FakeRag([chunk])
    )
    result = use_case.execute(1, "question")

    assert result.has_knowledge_base is True
    assert len(result.hits) == 1
    assert result.hits[0].title == article.title
    assert result.hits[0].relevance == 0.9
    db.close()


def test_recommend_articles_groups_and_ranks():
    db, articles, library = _setup()
    article = _article(articles, library.id, "10.2/d", 2023, "Abstract D")
    chunks = [
        RagContextChunk(
            chunk_id=1,
            document_id=77,
            knowledge_base_id=1,
            document_name="doc",
            chunk_index=0,
            text="first",
            rerank_score=0.5,
        ),
        RagContextChunk(
            chunk_id=2,
            document_id=77,
            knowledge_base_id=1,
            document_name="doc",
            chunk_index=1,
            text="second",
            rerank_score=0.8,
        ),
    ]

    class _ArticlesWithDocument:
        def get_by_document(self, library_id, document_id):
            return article if document_id == 77 else None

    use_case = RecommendResearchArticlesUseCase(
        _FakeEnsureLibrary(library), _ArticlesWithDocument(), _FakeRag(chunks)
    )
    result = use_case.execute(1, "what to read?")

    assert len(result.articles) == 1
    assert result.articles[0].score == 0.8
    assert len(result.articles[0].snippets) == 2
    db.close()


def test_summarize_articles_stores_summary():
    db, articles, library = _setup()
    _article(articles, library.id, "10.2/e", 2021, "Abstract E")
    provider = _FakeProvider("Готовая сводка")
    use_case = SummarizeResearchArticlesUseCase(
        ensure_library=_FakeEnsureLibrary(library),
        article_repository=articles,
        document_repository=SqliteDocumentRepository(db.get_session, object()),
        llm_registry=_FakeRegistry(provider),
        provider_name="fake",
        model_id="fake-model",
        max_source_chars=10000,
    )

    result = use_case.execute(1, ["10.2/e"])

    assert result.results[0].ok is True
    stored = articles.get_by_identifier(library.id, "10.2/e")
    assert stored.summary == "Готовая сводка"
    assert provider.calls == 1
    db.close()


def test_summarize_article_without_text_reports_error():
    db, articles, library = _setup()
    _article(articles, library.id, "10.2/f", 2021, "")
    use_case = SummarizeResearchArticlesUseCase(
        ensure_library=_FakeEnsureLibrary(library),
        article_repository=articles,
        document_repository=SqliteDocumentRepository(db.get_session, object()),
        llm_registry=_FakeRegistry(_FakeProvider()),
        provider_name="fake",
        model_id=None,
        max_source_chars=10000,
    )

    result = use_case.execute(1, ["10.2/f"])

    assert result.results[0].ok is False
    assert "текста" in (result.results[0].error or "")
    db.close()
