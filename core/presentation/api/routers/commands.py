"""Эндпоинты ассистентских команд (/help, /support).

Команда готовит контекст (база знаний + MCP-сервер) и передаёт вопрос агенту.
Presentation остаётся DTO-only: работа идёт через use cases, схемы — из
``core.presentation.api.schemas``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import (
    CommandRequest,
    CommandResponse,
    MessageResponse,
)

router = APIRouter(tags=["commands"])

_HELP = "/help"
_SUPPORT = "/support"


def _get_chat_or_404(uc: UseCasesDep, chat_id: int) -> None:
    if uc.select_chat.get_chat(chat_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Чат #{chat_id} не найден",
        )


def _parse_support_argument(argument: str) -> tuple[str | None, str]:
    """Разбирает ``[тикет] <вопрос>``: возвращает (тикет, вопрос)."""
    text = argument.strip()
    if not text:
        return None, ""
    parts = text.split(maxsplit=1)
    first = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    if first.lower().startswith(("t-", "u-", "ticket")):
        return first, rest
    return None, text


@router.post("/chats/{chat_id}/commands", response_model=CommandResponse)
def run_command(chat_id: int, request: CommandRequest, uc: UseCasesDep):
    """Выполняет ассистентскую команду для чата."""
    _get_chat_or_404(uc, chat_id)

    text = request.command.strip()
    name, _, raw_argument = text.partition(" ")
    name = name.lower()
    argument = raw_argument.strip()

    if name == _HELP:
        messages = uc.prepare_project_context.execute(chat_id)
        question = argument
        hint = (
            "[INFO] Задайте вопрос о проекте: /help <вопрос>. "
            "Например: /help как устроена архитектура проекта?"
        )
    elif name == _SUPPORT:
        messages = uc.prepare_support_context.execute(chat_id)
        ticket_id, question = _parse_support_argument(argument)
        if ticket_id and question:
            question = f"Тикет {ticket_id}. {question}"
        hint = (
            "[INFO] Задайте вопрос поддержки: /support [тикет] <вопрос>. "
            "Например: /support T-1001 почему не работает авторизация?"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестная команда: '{name}'",
        )

    if not question:
        messages.append(hint)
        return CommandResponse(messages=messages, response=None)

    answer = uc.send_message.execute(chat_id, question)
    return CommandResponse(
        messages=messages, response=MessageResponse.model_validate(answer)
    )
