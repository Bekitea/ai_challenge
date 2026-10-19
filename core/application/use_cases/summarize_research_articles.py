from __future__ import annotations

from core.application.dtos.research_summary_result_dto import (
    ArticleSummaryResultDTO,
    SummarizeArticlesResultDTO,
)
from core.application.protocols.document_repository import DocumentRepository
from core.application.protocols.llm_registry import LlmRegistry
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)
from core.domain.entities.research_article import ResearchArticle
from core.domain.protocols.llm_provider import LlmProvider

SUMMARY_SYSTEM_PROMPT = """\
Ты — научный ассистент, который готовит структурированные сводки статей для \
диссертационного исследования. Пиши на русском языке, кратко и по делу. \
Не выдумывай факты, которых нет в тексте; если данных нет, пиши «не указано».

Структура ответа:
1. Проблема и цель.
2. Метод и данные.
3. Ключевые результаты.
4. Ограничения.
5. Вклад и связь с исследованием пользователя (если задан фокус).
"""


class SummarizeResearchArticlesUseCase:
    """Генерирует и сохраняет сводки статей активной библиотеки чата."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
        document_repository: DocumentRepository,
        llm_registry: LlmRegistry,
        provider_name: str | None,
        model_id: str | None,
        max_source_chars: int,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository
        self._documents = document_repository
        self._registry = llm_registry
        self._provider_name = (provider_name or "").strip()
        self._model_id = (model_id or "").strip() or None
        self._max_source_chars = max(2000, max_source_chars)

    def execute(
        self,
        agent_id: int,
        identifiers: list[str] | None = None,
        *,
        only_missing: bool = True,
        focus: str | None = None,
        limit: int = 10,
        library_name: str | None = None,
    ) -> SummarizeArticlesResultDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        provider, model_id = self._resolve_provider()

        articles: list[ResearchArticle] = []
        if identifiers:
            for identifier in identifiers:
                article = self._articles.get_by_identifier(
                    library.id, identifier
                )
                if article is None:
                    articles.append(
                        ResearchArticle(
                            id=None,
                            library_id=library.id,
                            title=identifier,
                            status="error",
                            error_message="Статья не найдена в библиотеке.",
                        )
                    )
                else:
                    articles.append(article)
        else:
            candidates = self._articles.list(library.id, limit=500)
            if only_missing:
                candidates = [
                    article for article in candidates if not article.summary
                ]
            articles = candidates[: max(1, min(limit, 50))]

        results: list[ArticleSummaryResultDTO] = []
        for article in articles:
            if article.id is None:
                results.append(
                    ArticleSummaryResultDTO(
                        article_id=0,
                        title=article.title,
                        ok=False,
                        error=article.error_message,
                    )
                )
                continue
            results.append(self._summarize(article, provider, model_id, focus))
        return SummarizeArticlesResultDTO(results=results)

    def _summarize(
        self,
        article: ResearchArticle,
        provider: LlmProvider,
        model_id: str | None,
        focus: str | None,
    ) -> ArticleSummaryResultDTO:
        source_text = self._source_text(article)
        if not source_text:
            return ArticleSummaryResultDTO(
                article_id=article.id or 0,
                title=article.title,
                ok=False,
                error="Нет доступного текста или аннотации для сводки.",
            )

        focus_line = (
            f"\nФокус исследования пользователя: {focus.strip()}"
            if focus and focus.strip()
            else ""
        )
        metadata = self._metadata_line(article)
        prompt = (
            f"{metadata}{focus_line}\n\n"
            f"Материал статьи:\n{source_text}\n\n"
            "Подготовь структурированную сводку по указанной структуре."
        )
        try:
            response = provider.generate(
                [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
                timeout=300,
                model_id=model_id,
            )
        except Exception as exc:  # noqa: BLE001 - ошибка одной статьи не валит пакет
            return ArticleSummaryResultDTO(
                article_id=article.id or 0,
                title=article.title,
                ok=False,
                error=f"Ошибка LLM: {exc}",
            )

        summary = (response.content or "").strip()
        if not summary:
            return ArticleSummaryResultDTO(
                article_id=article.id or 0,
                title=article.title,
                ok=False,
                error="LLM вернула пустую сводку.",
            )
        updated = self._articles.set_summary(
            article.id, summary, self._model_id or provider.provider_name
        )
        return ArticleSummaryResultDTO(
            article_id=article.id or 0,
            title=article.title,
            ok=True,
            summary=updated.summary if updated else summary,
        )

    @staticmethod
    def _metadata_line(article: ResearchArticle) -> str:
        authors = ", ".join(article.authors) if article.authors else "не указаны"
        parts = [
            f"Название: {article.title}",
            f"Авторы: {authors}",
            f"Год: {article.publication_year or 'не указан'}",
        ]
        if article.venue:
            parts.append(f"Журнал: {article.venue}")
        if article.doi:
            parts.append(f"DOI: {article.doi}")
        return "\n".join(parts)

    def _source_text(self, article: ResearchArticle) -> str:
        chunks = (
            self._documents.list_chunks(article.document_id)
            if article.document_id is not None
            else []
        )
        parts: list[str] = []
        if article.abstract:
            parts.append("Аннотация:\n" + article.abstract.strip())
        if chunks:
            selected = chunks[:6]
            tail = [chunk for chunk in chunks[-2:] if chunk not in selected]
            selected.extend(tail)
            text = "\n\n".join(chunk.text for chunk in selected)
            parts.append("Фрагменты полного текста:\n" + text)
        joined = "\n\n".join(parts).strip()
        return joined[: self._max_source_chars]

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
