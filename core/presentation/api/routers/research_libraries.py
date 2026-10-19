"""REST API научных библиотек: активная библиотека чата, переключение, удаление."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import (
    CreateResearchLibraryRequest,
    ResearchArticlesPage,
    ResearchLibrary,
    ResearchLibraryBindingResult,
    ResearchLibraryOperationResult,
    SwitchResearchLibraryRequest,
)

router = APIRouter(tags=["research-libraries"])


def _get_chat_or_404(uc: UseCasesDep, chat_id: int) -> None:
    if uc.select_chat.get_chat(chat_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Чат #{chat_id} не найден",
        )


def _find_library(uc: UseCasesDep, name: str):
    clean = (name or "").strip().casefold()
    for library in uc.research_list_libraries.execute():
        if library.name.strip().casefold() == clean:
            return library
    return None


@router.get("/chats/{chat_id}/library", response_model=ResearchLibrary | None)
def get_active_library(chat_id: int, uc: UseCasesDep):
    """Активная научная библиотека чата (без автосоздания)."""
    _get_chat_or_404(uc, chat_id)
    return uc.research_get_active_library.execute(chat_id)


@router.get(
    "/chats/{chat_id}/library/available",
    response_model=list[ResearchLibrary],
)
def list_available_libraries(chat_id: int, uc: UseCasesDep):
    """Все научные библиотеки, доступные для подключения."""
    _get_chat_or_404(uc, chat_id)
    return uc.research_list_libraries.execute()


def _list_articles(
    uc: UseCasesDep,
    library_id: int,
    query: str | None,
    year_from: int | None,
    year_to: int | None,
    article_status: str | None,
    limit: int,
    offset: int,
) -> ResearchArticlesPage:
    try:
        return uc.research_list_library_articles.execute(
            library_id,
            query=query,
            year_from=year_from,
            year_to=year_to,
            status=article_status,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/chats/{chat_id}/library/articles",
    response_model=ResearchArticlesPage,
)
def list_chat_library_articles(
    chat_id: int,
    uc: UseCasesDep,
    query: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Статьи активной научной библиотеки чата."""
    _get_chat_or_404(uc, chat_id)
    library = uc.research_get_active_library.execute(chat_id)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="У чата нет активной научной библиотеки",
        )
    return _list_articles(
        uc,
        library.id,
        query,
        year_from,
        year_to,
        status_filter,
        limit,
        offset,
    )


@router.get(
    "/libraries/{library_id}/articles",
    response_model=ResearchArticlesPage,
)
def list_library_articles(
    library_id: int,
    uc: UseCasesDep,
    query: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Статьи научной библиотеки по её id."""
    return _list_articles(
        uc,
        library_id,
        query,
        year_from,
        year_to,
        status_filter,
        limit,
        offset,
    )


@router.post(
    "/chats/{chat_id}/library/switch",
    response_model=ResearchLibraryBindingResult,
)
def switch_library(
    chat_id: int, request: SwitchResearchLibraryRequest, uc: UseCasesDep
):
    """Подключить существующую библиотеку к чату (вместе с её БЗ)."""
    _get_chat_or_404(uc, chat_id)
    library = _find_library(uc, request.name)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Научная библиотека '{request.name}' не найдена",
        )
    return uc.research_bind_library.execute(chat_id, library.id)


@router.post(
    "/chats/{chat_id}/library/create",
    response_model=ResearchLibrary,
    status_code=status.HTTP_201_CREATED,
)
def create_library(
    chat_id: int, request: CreateResearchLibraryRequest, uc: UseCasesDep
):
    """Создать научную библиотеку и подключить её к чату."""
    _get_chat_or_404(uc, chat_id)
    return uc.research_create_library.execute(
        chat_id,
        request.name,
        description=request.description,
        goal=request.goal,
        field=request.field,
        keywords=request.keywords,
        year_from=request.year_from,
        year_to=request.year_to,
        language=request.language,
    )


@router.delete(
    "/chats/{chat_id}/library",
    response_model=ResearchLibraryOperationResult,
)
def detach_library(chat_id: int, uc: UseCasesDep):
    """Открепить активную библиотеку от чата (данные сохраняются)."""
    _get_chat_or_404(uc, chat_id)
    return uc.research_detach_library.execute(chat_id)


@router.delete(
    "/libraries/{library_id}",
    response_model=ResearchLibraryOperationResult,
)
def delete_library(library_id: int, confirm_name: str, uc: UseCasesDep):
    """Удалить библиотеку глобально (требуется точное имя для подтверждения)."""
    libraries = uc.research_list_libraries.execute()
    library = next((item for item in libraries if item.id == library_id), None)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Научная библиотека #{library_id} не найдена",
        )
    return uc.research_delete_library.execute(library.name, confirm_name)
