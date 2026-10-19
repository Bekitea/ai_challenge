#!/usr/bin/env python3
"""MCP-сервер научной библиотеки для диссертационного агента.

У каждого чата своя библиотека статей и своя база знаний RAG. Текущий чат
передаётся презентацией через переменную окружения ``AI_CHAT_AGENT_ID``.
Сервер stateless: каждый вызов инструмента — отдельный процесс, поэтому все
результаты сохраняются в БД, а не в памяти процесса.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Скрипт запускается как отдельный процесс из папки mcp/, поэтому корень
# проекта нужно явно добавить в sys.path до импорта core.*.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server import MCPServer

import config
from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.dtos.research_article_dto import ResearchArticleDTO
from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.di.app_factory import initialize_application

mcp = MCPServer("ResearchLibrary")

_bundle = None


def _get_bundle():
    global _bundle
    if _bundle is None:
        _bundle = initialize_application()
    return _bundle


def _agent_id() -> int | None:
    raw = os.environ.get("AI_CHAT_AGENT_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _require_agent_id() -> int:
    agent_id = _agent_id()
    if agent_id is None:
        raise ValueError(
            "Не передан AI_CHAT_AGENT_ID: research-инструменты работают "
            "только из чата, к которому привязана научная библиотека."
        )
    return agent_id


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _json(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, indent=2)


def _error(exc: BaseException) -> str:
    return f"[ERROR] {type(exc).__name__}: {exc}"


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def _library_payload(library: ResearchLibraryDTO) -> dict[str, Any]:
    payload = _jsonable(library)
    payload["knowledge_base_name"] = _knowledge_base_name(library)
    return payload


def _knowledge_base_name(library: ResearchLibraryDTO) -> str | None:
    bundle = _get_bundle()
    if library.knowledge_base_id is None:
        return None
    for kb in bundle.list_knowledge_bases.execute():
        if kb.id == library.knowledge_base_id:
            return kb.name
    return None


def _candidate_payload(
    candidate: ArticleCandidateDTO, abstract_limit: int = 2000
) -> dict[str, Any]:
    payload = _jsonable(candidate)
    payload["abstract"] = _truncate(candidate.abstract, abstract_limit)
    return payload


def _article_payload(
    article: ResearchArticleDTO,
    abstract_limit: int = 1500,
    summary_limit: int = 4000,
) -> dict[str, Any]:
    payload = _jsonable(article)
    payload["abstract"] = _truncate(article.abstract, abstract_limit)
    payload["summary"] = _truncate(article.summary, summary_limit)
    return payload


def _resolve_library(library_name: str | None) -> ResearchLibraryDTO:
    return _get_bundle().research_ensure_library.execute(
        _require_agent_id(), library_name
    )


@mcp.tool()
def create_library(
    name: str,
    goal: str | None = None,
    field: str | None = None,
    keywords: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    language: str | None = None,
    description: str | None = None,
) -> str:
    """Создать научную библиотеку для текущего чата и сделать её активной.

    Используйте, когда начинаете новую научную область/диссертацию. Каждая
    библиотека имеет собственную базу знаний RAG и не смешивается с другими
    чатами. После создания сразу заполните профиль (goal/field/keywords), чтобы
    поиск и генерация гипотез учитывали контекст.
    """
    try:
        bundle = _get_bundle()
        library = bundle.research_create_library.execute(
            _require_agent_id(),
            name,
            description=description,
            goal=goal,
            field=field,
            keywords=keywords,
            year_from=year_from,
            year_to=year_to,
            language=language,
        )
        return _json(_library_payload(library))
    except Exception as exc:  # noqa: BLE001 - инструмент возвращает текст ошибки
        return _error(exc)


@mcp.tool()
def list_libraries() -> str:
    """Показать все научные библиотеки: имя, область, число статей, id БЗ.

    Помогает понять, какие библиотеки уже существуют, и выбрать имя для
    switch_library.
    """
    try:
        libraries = _get_bundle().research_list_libraries.execute()
        return _json([_library_payload(library) for library in libraries])
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def switch_library(name: str) -> str:
    """Сделать существующую научную библиотеку активной для текущего чата.

    Используйте, когда в чате нужно продолжить работу с библиотекой,
    созданной ранее (в этом или другом чате).
    """
    try:
        library = _get_bundle().research_switch_library.execute(
            _require_agent_id(), name
        )
        return _json(_library_payload(library))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def get_library_info(library: str | None = None) -> str:
    """Показать профиль активной научной библиотеки текущего чата.

    ``library`` — необязательное имя другой библиотеки для разового просмотра.
    """
    try:
        return _json(_library_payload(_resolve_library(library)))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def update_library_profile(
    name: str | None = None,
    description: str | None = None,
    goal: str | None = None,
    field: str | None = None,
    keywords: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    language: str | None = None,
) -> str:
    """Обновить имя и профиль активной научной библиотеки.

    Заполните цель диссертации (goal), область (field), ключевые слова и
    диапазон лет — эти значения используются по умолчанию при поиске и в
    контексте для обзора/гипотез. Незаданные параметры не меняются.
    """
    try:
        library = _get_bundle().research_update_profile.execute(
            _require_agent_id(),
            name=name,
            description=description,
            goal=goal,
            field=field,
            keywords=keywords,
            year_from=year_from,
            year_to=year_to,
            language=language,
        )
        return _json(_library_payload(library))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def detach_library() -> str:
    """Открепить активную научную библиотеку от текущего чата.

    Библиотека, её статьи и БЗ сохраняются и могут быть подключены к другому
    чату через switch_library. От чата отключается только БЗ этой библиотеки.
    """
    try:
        result = _get_bundle().research_detach_library.execute(
            _require_agent_id()
        )
        return _json(result)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def delete_library(name: str, confirm_name: str) -> str:
    """Полностью удалить научную библиотеку (необратимо).

    Удаляет привязки во всех чатах, статьи, метаданные, БЗ, документы, векторы
    и файлы. Для защиты требуется confirm_name, точно совпадающее с name.
    """
    try:
        result = _get_bundle().research_delete_library.execute(name, confirm_name)
        return _json(result)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def search_articles(
    query: str,
    year_from: int | None = None,
    year_to: int | None = None,
    limit: int | None = None,
    sort: str = "relevance",
    language: str | None = None,
    oa_only: bool = True,
    library: str | None = None,
) -> str:
    """Найти научные статьи в OpenAlex в контексте активной библиотеки.

    Параметры:
        query: тема/ключевые слова (лучше на английском).
        year_from, year_to: диапазон лет; если не заданы, берутся из профиля.
        sort: relevance | cited | recent.
        oa_only: только открытый доступ (по умолчанию true).
        library: имя другой библиотеки для разового поиска.

    Возвращает метаданные (название, авторы, год, DOI, журнал, аннотацию,
    ссылки на PDF) и признаки in_library/library_status. Ничего не сохраняет:
    для добавления в библиотеку вызовите import_articles с DOI/OpenAlex ID.
    """
    try:
        result = _get_bundle().research_search_articles.execute(
            _require_agent_id(),
            query,
            year_from=year_from,
            year_to=year_to,
            limit=limit,
            sort=sort,
            language=language,
            oa_only=oa_only,
            library_name=library,
        )
        return _json(
            {
                "library": _library_payload(result.library),
                "query": result.query,
                "year_from": result.year_from,
                "year_to": result.year_to,
                "total": result.total,
                "articles": [
                    _candidate_payload(candidate)
                    for candidate in result.articles
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def import_articles(
    identifiers: list[str],
    force: bool = False,
    library: str | None = None,
) -> str:
    """Добавить найденные статьи в библиотеку текущего чата.

    Принимает DOI или OpenAlex ID (до 5 за вызов). Для каждой статьи:
    скачивает OA-PDF из открытого доступа и индексирует полный текст; если PDF
    недоступен — индексирует аннотацию. Метаданные сохраняются в библиотеке,
    при повторном импорте дубликат не создаётся. ``force=True`` переиндексирует
    уже добавленную статью. Используйте идентификаторы из search_articles.
    """
    try:
        result = _get_bundle().research_import_articles.execute(
            _require_agent_id(),
            identifiers,
            force=force,
            library_name=library,
        )
        return _json(
            {
                "library": _library_payload(result.library),
                "results": [_jsonable(item) for item in result.results],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def list_articles(
    query: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    library: str | None = None,
) -> str:
    """Показать статьи только активной научной библиотеки текущего чата.

    Фильтры: подстрока query (название/аннотация/авторы), годы, статус
    (candidate/downloaded/indexed/abstract_only/error). Используйте перед
    обзором, чтобы понять состав библиотеки.
    """
    try:
        articles = _get_bundle().research_list_articles.execute(
            _require_agent_id(),
            query=query,
            year_from=year_from,
            year_to=year_to,
            status=status,
            limit=limit,
            offset=offset,
            library_name=library,
        )
        return _json(
            {
                "library": _library_payload(_resolve_library(library)),
                "count": len(articles),
                "offset": offset,
                "articles": [
                    _article_payload(article) for article in articles
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def get_article(identifier: str, library: str | None = None) -> str:
    """Показать статью по DOI или OpenAlex ID.

    Сначала ищет в активной библиотеке (метаданные, статус, сводка). Если
    статьи там нет, возвращает метаданные из OpenAlex с in_library=false.
    """
    try:
        article = _get_bundle().research_get_article.execute(
            _require_agent_id(), identifier, library_name=library
        )
        if isinstance(article, ResearchArticleDTO):
            return _json(_article_payload(article, abstract_limit=4000))
        return _json(_candidate_payload(article, abstract_limit=4000))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def get_library_stats(library: str | None = None) -> str:
    """Статистика активной библиотеки: всего статей, статусы, годы, сводки."""
    try:
        stats = _get_bundle().research_stats.execute(
            _require_agent_id(), library_name=library
        )
        return _json(stats)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def summarize_articles(
    identifiers: list[str] | None = None,
    only_missing: bool = True,
    focus: str | None = None,
    limit: int = 10,
    library: str | None = None,
) -> str:
    """Подготовить структурированные сводки статей библиотеки.

    Если identifiers не заданы, обрабатываются статьи без сводки (only_missing)
    или первые limit статей. ``focus`` помогает связать сводку с целью
    диссертации. Сводки сохраняются в библиотеке и затем используются в
    get_review_context/get_hypothesis_context.
    """
    try:
        result = _get_bundle().research_summarize_articles.execute(
            _require_agent_id(),
            identifiers,
            only_missing=only_missing,
            focus=focus,
            limit=limit,
            library_name=library,
        )
        return _json(result)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def search_library(
    query: str,
    top_k: int = 8,
    year_from: int | None = None,
    year_to: int | None = None,
    library: str | None = None,
) -> str:
    """RAG-поиск по базе знаний активной библиотеки (для ответов на вопросы).

    Возвращает релевантные фрагменты статей с цитатными метаданными
    (название, авторы, год, DOI) и оценкой релевантности. Отвечайте только по
    найденным фрагментам; если данных нет — скажите об этом.
    """
    try:
        hits = _get_bundle().research_search_library.execute(
            _require_agent_id(),
            query,
            top_k=top_k,
            year_from=year_from,
            year_to=year_to,
            library_name=library,
        )
        return _json(hits)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def recommend_articles(
    question: str,
    top_k: int = 10,
    year_from: int | None = None,
    year_to: int | None = None,
    library: str | None = None,
) -> str:
    """Подобрать статьи из библиотеки, которые стоит прочитать по вопросу.

    Возвращает статьи, сгруппированные по документам, с оценкой релевантности,
    сводкой (если есть) и наиболее релевантными фрагментами. На основе этого
    объясните пользователю, что и в каком порядке читать.
    """
    try:
        result = _get_bundle().research_recommend_articles.execute(
            _require_agent_id(),
            question,
            top_k=top_k,
            year_from=year_from,
            year_to=year_to,
            library_name=library,
        )
        return _json(result)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def get_review_context(
    topic: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    max_chars: int | None = None,
    limit: int = 40,
    offset: int = 0,
    library: str | None = None,
) -> str:
    """Контекст для систематического обзора по активной библиотеке.

    Возвращает карточки статей (цитата, метаданные, сводка или аннотация) в
    пределах бюджета символов. Используйте для синтеза трендов, прогресса,
    достижений, методов и пробелов. При truncated=true запросите следующую
    страницу через offset.
    """
    try:
        context = _get_bundle().research_review_context.execute(
            _require_agent_id(),
            topic=topic,
            year_from=year_from,
            year_to=year_to,
            max_chars=max_chars or config.RESEARCH_REVIEW_MAX_CHARS,
            limit=limit,
            offset=offset,
            library_name=library,
        )
        return _json(context)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


@mcp.tool()
def get_hypothesis_context(
    goal: str | None = None,
    max_chars: int | None = None,
    limit: int = 30,
    library: str | None = None,
) -> str:
    """Контекст для генерации проверяемых гипотез по цели диссертации.

    Возвращает профиль библиотеки, сводки/аннотации статей и релевантные
    RAG-фрагменты. На основе этого предложите гипотезы с обоснованием, методом
    проверки, данными, метриками, рисками и ожидаемым вкладом.
    """
    try:
        context = _get_bundle().research_hypothesis_context.execute(
            _require_agent_id(),
            goal=goal,
            max_chars=max_chars or config.RESEARCH_SUMMARY_MAX_CHARS,
            limit=limit,
            library_name=library,
        )
        return _json(context)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


if __name__ == "__main__":
    mcp.run(transport="stdio")
