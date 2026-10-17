"""Эндпоинты управления MCP-серверами чата."""

from __future__ import annotations

from fastapi import APIRouter

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import (
    ActionResult,
    AvailableMcpServer,
    McpServerStatus,
)

router = APIRouter(tags=["mcp"])


@router.get("/chats/{chat_id}/mcp", response_model=list[McpServerStatus])
def list_connected(chat_id: int, uc: UseCasesDep):
    """Подключённые к чату MCP-серверы."""
    return uc.list_connected_mcp.execute(chat_id)


@router.get(
    "/chats/{chat_id}/mcp/available", response_model=list[AvailableMcpServer]
)
def list_available(chat_id: int, uc: UseCasesDep):
    """MCP-серверы, доступные для подключения."""
    return uc.list_available_mcp.execute(chat_id)


@router.post("/chats/{chat_id}/mcp/{server_name}", response_model=ActionResult)
def connect_mcp(
    chat_id: int, server_name: str, uc: UseCasesDep
):
    """Подключает MCP-сервер к чату."""
    success, message = uc.connect_mcp.execute(chat_id, server_name)
    return ActionResult(success=success, message=message)


@router.delete("/chats/{chat_id}/mcp/{server_name}", response_model=ActionResult)
def disconnect_mcp(
    chat_id: int, server_name: str, uc: UseCasesDep
):
    """Отключает MCP-сервер от чата."""
    success, message = uc.disconnect_mcp.execute(chat_id, server_name)
    return ActionResult(success=success, message=message)
