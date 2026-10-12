"""Эндпоинты чатов: список, создание, история, сообщения, настройки, фазы."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.deps import UseCasesDep
from api.schemas import (
    BranchRequest,
    ChangePhaseRequest,
    Chat,
    ChatInfo,
    ChatPreview,
    CreateChatRequest,
    HistoryMessage,
    MemorySaveResult,
    MessageResponse,
    PhaseChangeResult,
    RerankRequest,
    RerankResult,
    SendMessageRequest,
    Settings,
    SummaryResponse,
)
from use_cases import (
    SettingsDTO,
    StrategySelection,
    UseCasesBundle,
)

router = APIRouter(tags=["chats"])


def _get_chat_or_404(uc: UseCasesBundle, chat_id: int) -> Chat:
    chat = uc.select_chat.get_chat(chat_id)
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Чат #{chat_id} не найден",
        )
    return chat


def _settings_dto(settings: Settings) -> SettingsDTO:
    return SettingsDTO(**settings.model_dump())


@router.get("/chats", response_model=list[ChatPreview])
def list_chats(uc: UseCasesDep):
    """Список превью всех чатов."""
    return uc.select_chat.get_all_previews()


@router.post("/chats", response_model=Chat, status_code=status.HTTP_201_CREATED)
def create_chat(
    request: CreateChatRequest, uc: UseCasesDep
):
    """Создаёт новый чат с указанными настройками и стратегией."""
    if request.strategy is None:
        strategy = StrategySelection(strategy_type="DefaultStrategy")
    else:
        strategy = StrategySelection(**request.strategy.model_dump())
    return uc.create_chat.execute(
        name=request.name,
        system_prompt=request.system_prompt,
        settings=_settings_dto(request.settings),
        strategy_selection=strategy,
        task_profile_id=request.task_profile_id,
    )


@router.get("/chats/{chat_id}", response_model=Chat)
def get_chat(chat_id: int, uc: UseCasesDep):
    """Информация о чате."""
    return _get_chat_or_404(uc, chat_id)


@router.get("/chats/{chat_id}/history", response_model=list[HistoryMessage])
def get_history(chat_id: int, uc: UseCasesDep):
    """История сообщений чата."""
    _get_chat_or_404(uc, chat_id)
    return uc.show_history.execute(chat_id) or []


@router.get("/chats/{chat_id}/info", response_model=ChatInfo)
def get_info(chat_id: int, uc: UseCasesDep):
    """Информация о чате и счётчики токенов."""
    info = uc.show_chat_info.execute(chat_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Чат #{chat_id} не найден")
    return info


@router.get("/chats/{chat_id}/summary", response_model=SummaryResponse)
def get_summary(chat_id: int, uc: UseCasesDep):
    """Саммари диалога."""
    _get_chat_or_404(uc, chat_id)
    return SummaryResponse(summary=uc.show_summary.execute(chat_id))


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
def send_message(
    chat_id: int,
    request: SendMessageRequest,
    uc: UseCasesDep,
):
    """Отправляет сообщение агенту и возвращает ответ."""
    _get_chat_or_404(uc, chat_id)
    return uc.send_message.execute(chat_id, request.message)


@router.get("/chats/{chat_id}/settings", response_model=Settings)
def get_settings(chat_id: int, uc: UseCasesDep):
    """Текущие настройки чата."""
    settings = uc.view_settings.execute(chat_id)
    if settings is None:
        raise HTTPException(status_code=404, detail=f"Чат #{chat_id} не найден")
    return settings


@router.put("/chats/{chat_id}/settings", response_model=Settings)
def update_settings(
    chat_id: int, request: Settings, uc: UseCasesDep
):
    """Обновляет настройки чата."""
    _get_chat_or_404(uc, chat_id)
    uc.change_settings.execute(chat_id, _settings_dto(request))
    return uc.view_settings.execute(chat_id)


@router.post("/chats/{chat_id}/rerank", response_model=RerankResult)
def set_rerank(
    chat_id: int,
    request: RerankRequest,
    uc: UseCasesDep,
):
    """Включает или отключает реранкинг для чата."""
    _get_chat_or_404(uc, chat_id)
    enabled = uc.set_reranker_enabled.execute(chat_id, request.enabled)
    return RerankResult(enabled=enabled)


@router.post("/chats/{chat_id}/phase", response_model=PhaseChangeResult)
def change_phase(
    chat_id: int,
    request: ChangePhaseRequest,
    uc: UseCasesDep,
):
    """Переходит в другую фазу агента."""
    _get_chat_or_404(uc, chat_id)
    return uc.change_phase.execute(chat_id, request.command)


@router.post("/chats/{chat_id}/branch", response_model=Chat, status_code=201)
def create_branch(
    chat_id: int,
    request: BranchRequest,
    uc: UseCasesDep,
):
    """Создаёт ветку текущего чата."""
    _get_chat_or_404(uc, chat_id)
    return uc.create_branch.execute(chat_id, request.name)


@router.post("/chats/{chat_id}/memory/save", response_model=MemorySaveResult)
def save_memory(chat_id: int, uc: UseCasesDep):
    """Сохраняет память чата (глобальную и профиля задачи)."""
    _get_chat_or_404(uc, chat_id)
    return uc.save_agent_memory.execute(chat_id)
