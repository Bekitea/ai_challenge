from __future__ import annotations

from core.application.dtos.code_review_dto import (
    CodeReviewRequestDTO,
    CodeReviewResultDTO,
)
from core.application.dtos.rag_source_dto import RagSourceDTO
from core.application.protocols.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from core.application.protocols.llm_registry import LlmRegistry
from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.protocols.llm_provider import LlmProvider
from core.domain.protocols.rag_retriever import RagRetriever

REVIEW_SYSTEM_PROMPT = """\
Ты — опытный senior-инженер и архитектор, который проводит код-ревью pull \
request. Твоя задача — найти потенциальные баги, проблемы архитектуры и дать \
конкретные рекомендации. Опирайся на правила и конвенции проекта из контекста и \
на сам diff. Не выдумывай код, которого не видишь. Пиши на русском языке, \
конкретно и предметно.

Формат ответа (Markdown), строго три раздела:
## Потенциальные баги
## Архитектурные проблемы
## Рекомендации

Для каждой находки указывай файл (и, по возможности, строку), серьёзность \
(критично / важно / замечание), краткое пояснение и предлагаемое исправление. \
Если по разделу замечаний нет — напиши «Не обнаружено».
"""

REVIEW_USER_TEMPLATE = """\
Правила и контекст проекта (выдержки из базы знаний, могут быть неполными):
{context}

Метаданные pull request:
- Репозиторий: {repo}
- PR: #{pr_number} {pr_title}
- Автор: {author}
- Ветки: {head_branch} -> {base_branch}
- Изменённые файлы:
{changed_files}

Diff:
```diff
{diff}
```

Проведи ревью этого PR и верни ответ строго по заданной структуре.
"""

_EMPTY_CONTEXT = "(контекст не найден)"


class ReviewPullRequestUseCase:
    """Готовит AI-ревью pull request по diff и RAG-контексту проекта.

    Раннер CI передаёт готовый diff и метаданные PR; use case выполняет
    RAG-поиск по выделенной базе знаний (документация + код), собирает промпт
    и напрямую вызывает LLM-провайдер. Это stateless-операция: чат и история
    не создаются.
    """

    def __init__(
        self,
        *,
        rag_service: RagRetriever,
        knowledge_base_repository: KnowledgeBaseRepository,
        llm_registry: LlmRegistry,
        knowledge_base_name: str,
        provider_name: str | None = None,
        model_id: str | None = None,
        top_k: int = 8,
        max_diff_chars: int = 60000,
        max_tokens: int = 2000,
        timeout: int = 300,
    ):
        self._rag_service = rag_service
        self._kb_repository = knowledge_base_repository
        self._registry = llm_registry
        self._kb_name = knowledge_base_name
        self._provider_name = (provider_name or "").strip()
        self._model_id = (model_id or "").strip() or None
        self._top_k = max(1, top_k)
        self._max_diff_chars = max(2000, max_diff_chars)
        self._max_tokens = max(256, max_tokens)
        self._timeout = timeout

    def execute(self, request: CodeReviewRequestDTO) -> CodeReviewResultDTO:
        """Возвращает Markdown-ревью и использованные RAG-источники.

        Args:
            request: Diff и метаданные pull request.

        Returns:
            CodeReviewResultDTO: текст ревью, источники и статистика токенов.
        """
        chunks = self._retrieve_context(request)
        prompt = self._build_prompt(request, chunks)
        provider, model_id = self._resolve_provider()

        response = provider.generate(
            [
                {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=self._max_tokens,
            timeout=self._timeout,
            model_id=model_id,
        )

        review = (response.content or "").strip()
        if not review:
            review = (
                "## Потенциальные баги\nНе обнаружено.\n\n"
                "## Архитектурные проблемы\nНе обнаружено.\n\n"
                "## Рекомендации\nLLM вернула пустой ответ."
            )

        return CodeReviewResultDTO(
            review=review,
            rag_sources=[self._to_source(chunk) for chunk in chunks],
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=self._model_id or provider.provider_name,
        )

    def _retrieve_context(self, request: CodeReviewRequestDTO) -> list[RagContextChunk]:
        knowledge_base = self._find_knowledge_base()
        if knowledge_base is None:
            return []

        query = self._build_query(request)
        if not query:
            return []
        return self._rag_service.search_knowledge_base(
            knowledge_base.id, query, self._top_k
        )

    def _find_knowledge_base(self):
        for knowledge_base in self._kb_repository.list():
            if knowledge_base.name == self._kb_name:
                return knowledge_base
        return None

    @staticmethod
    def _build_query(request: CodeReviewRequestDTO) -> str:
        parts = [request.pr_title.strip()]
        if request.changed_files:
            parts.append("Изменённые файлы: " + ", ".join(request.changed_files))
        return "\n".join(part for part in parts if part).strip()

    def _build_prompt(
        self, request: CodeReviewRequestDTO, chunks: list[RagContextChunk]
    ) -> str:
        return REVIEW_USER_TEMPLATE.format(
            context=self._format_context(chunks),
            repo=request.repo or "(не указан)",
            pr_number=request.pr_number if request.pr_number is not None else "?",
            pr_title=request.pr_title or "(без названия)",
            author=request.author or "(не указан)",
            head_branch=request.head_branch or "(не указана)",
            base_branch=request.base_branch or "(не указана)",
            changed_files=self._format_changed_files(request.changed_files),
            diff=self._truncate_diff(request.diff),
        )

    @staticmethod
    def _format_context(chunks: list[RagContextChunk]) -> str:
        if not chunks:
            return _EMPTY_CONTEXT
        blocks = []
        for index, chunk in enumerate(chunks, start=1):
            blocks.append(
                f"[{index}] {chunk.document_name} (фрагмент {chunk.chunk_index}):\n"
                f"{chunk.text.strip()}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _format_changed_files(changed_files: list[str]) -> str:
        if not changed_files:
            return "  (список не передан)"
        return "\n".join(f"  - {name}" for name in changed_files)

    def _truncate_diff(self, diff: str) -> str:
        text = (diff or "").strip()
        if not text:
            return "(diff пуст)"
        if len(text) <= self._max_diff_chars:
            return text
        omitted = len(text) - self._max_diff_chars
        return (
            text[: self._max_diff_chars]
            + f"\n\n... [diff обрезан, пропущено {omitted} символов] ..."
        )

    @staticmethod
    def _to_source(chunk: RagContextChunk) -> RagSourceDTO:
        return RagSourceDTO(
            document_name=chunk.document_name,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            relevance=chunk.relevance,
        )

    def _resolve_provider(self) -> tuple[LlmProvider, str | None]:
        providers = self._registry.all()
        if not providers:
            raise ValueError("Нет доступных LLM-провайдеров.")
        if self._provider_name:
            provider = providers.get(self._provider_name)
            if provider is not None:
                return provider, self._model_id
        provider = next(iter(providers.values()))
        return provider, None
