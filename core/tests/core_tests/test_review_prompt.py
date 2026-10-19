"""Сборка промпта и обрезка diff в use case ревью PR (UC-032)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

os.environ["APPLICATION_MODE"] = "TEST"

from core.application.dtos.code_review_dto import CodeReviewRequestDTO
from core.application.dtos.knowledge_base_dto import KnowledgeBaseDTO
from core.application.use_cases.review_pull_request import (
    ReviewPullRequestUseCase,
)
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.rag_context_chunk import RagContextChunk


class _FakeKnowledgeBaseRepository:
    def __init__(self, knowledge_bases: list[KnowledgeBaseDTO]):
        self._knowledge_bases = knowledge_bases

    def list(self) -> list[KnowledgeBaseDTO]:
        return list(self._knowledge_bases)


def _kb(kb_id: int, name: str) -> KnowledgeBaseDTO:
    now = datetime.now(UTC)
    return KnowledgeBaseDTO(
        id=kb_id,
        name=name,
        description=None,
        embedding_model="bge-m3",
        embedding_dimension=1024,
        created_at=now,
    )


class _FakeRagService:
    def __init__(self, chunks: list[RagContextChunk]):
        self._chunks = chunks
        self.queries: list[tuple[int, str, int | None]] = []

    def search_knowledge_base(
        self, knowledge_base_id: int, query_text: str, top_k: int | None = None
    ) -> list[RagContextChunk]:
        self.queries.append((knowledge_base_id, query_text, top_k))
        return list(self._chunks)


class _FakeProvider:
    provider_name = "fake"

    def __init__(self):
        self.messages: list[list[dict]] = []

    def generate(self, messages, **kwargs) -> LlmResponse:
        self.messages.append(messages)
        return LlmResponse(
            content="## Потенциальные баги\nНе обнаружено.",
            prompt_tokens=11,
            completion_tokens=7,
        )


class _FakeRegistry:
    def __init__(self, provider: _FakeProvider):
        self._provider = provider

    def get(self, name: str):
        return self._provider if name == "fake" else None

    def all(self) -> dict:
        return {"fake": self._provider}


def _chunk() -> RagContextChunk:
    return RagContextChunk(
        chunk_id=1,
        document_id=2,
        knowledge_base_id=3,
        document_name="docs/architecture.md",
        chunk_index=0,
        text="Presentation остаётся DTO-only.",
    )


def _build(**overrides) -> tuple[
    ReviewPullRequestUseCase, _FakeRagService, _FakeProvider
]:
    provider = _FakeProvider()
    rag = _FakeRagService(overrides.pop("chunks", [_chunk()]))
    use_case = ReviewPullRequestUseCase(
        rag_service=rag,
        knowledge_base_repository=_FakeKnowledgeBaseRepository(
            overrides.pop("knowledge_bases", [_kb(3, "Ревью кода")])
        ),
        llm_registry=_FakeRegistry(provider),
        knowledge_base_name="Ревью кода",
        top_k=overrides.pop("top_k", 5),
        max_diff_chars=overrides.pop("max_diff_chars", 60000),
    )
    return use_case, rag, provider


def _request(diff: str = "+new line") -> CodeReviewRequestDTO:
    return CodeReviewRequestDTO(
        repo="acme/repo",
        pr_number=7,
        pr_title="Починить RAG",
        author="dev",
        base_branch="main",
        head_branch="fix/rag",
        changed_files=["core/rag.py"],
        diff=diff,
    )


def test_prompt_includes_diff_context_and_metadata():
    """Промпт содержит diff, RAG-контекст и метаданные PR, а источники — в ответе."""
    use_case, rag, provider = _build()

    result = use_case.execute(_request())

    assert result.review.startswith("## Потенциальные баги")
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert len(result.rag_sources) == 1
    assert result.rag_sources[0].document_name == "docs/architecture.md"

    user_prompt = provider.messages[0][1]["content"]
    assert "+new line" in user_prompt
    assert "Presentation остаётся DTO-only." in user_prompt
    assert "core/rag.py" in user_prompt
    assert "#7" in user_prompt

    assert rag.queries == [(3, "Починить RAG\nИзменённые файлы: core/rag.py", 5)]


def test_long_diff_is_truncated():
    """Слишком длинный diff обрезается, чтобы не переполнить контекст LLM."""
    use_case, _, provider = _build(max_diff_chars=2000, chunks=[])

    result = use_case.execute(_request(diff="x" * 5000))

    user_prompt = provider.messages[0][1]["content"]
    assert "diff обрезан" in user_prompt
    assert result.rag_sources == []


def test_missing_knowledge_base_skips_rag():
    """Если review-БЗ не найдена, RAG не выполняется и источников нет."""
    use_case, rag, _ = _build(knowledge_bases=[_kb(1, "Другая БЗ")])

    result = use_case.execute(_request())

    assert result.rag_sources == []
    assert rag.queries == []
