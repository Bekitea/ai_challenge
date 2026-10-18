#!/usr/bin/env python3
"""MCP-сервер поддержки пользователей (CRM-заглушка).

Данные о пользователях и тикетах читаются из JSON-файла (по умолчанию
``mcp/data/support_seed.json``, путь переопределяется переменной окружения
``SUPPORT_DATA_PATH``). Инструменты позволяют получить контекст тикета и
пользователя, чтобы ассистент отвечал с учётом обращения.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "mcp" / "data" / "support_seed.json"

mcp = MCPServer(
    "SupportCRM",
    description="Пользователи и тикеты поддержки (CRM) из локального JSON.",
)


def _data_path() -> Path:
    override = os.getenv("SUPPORT_DATA_PATH")
    return Path(override) if override else DEFAULT_DATA_PATH


def _load_data() -> dict[str, Any]:
    path = _data_path()
    if not path.is_file():
        return {"users": [], "tickets": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"users": [], "tickets": []}


def _users() -> list[dict[str, Any]]:
    return list(_load_data().get("users", []))


def _tickets() -> list[dict[str, Any]]:
    return list(_load_data().get("tickets", []))


def _find_user_by_id(user_id: str) -> dict[str, Any] | None:
    for user in _users():
        if str(user.get("id")) == str(user_id):
            return user
    return None


def _format_user(user: dict[str, Any] | None) -> str:
    if not user:
        return "Пользователь не найден."
    return (
        f"ID: {user.get('id')}\n"
        f"Имя: {user.get('name')}\n"
        f"Email: {user.get('email')}\n"
        f"Тариф: {user.get('plan')}\n"
        f"Зарегистрирован: {user.get('created_at')}"
    )


def _format_ticket(ticket: dict[str, Any], user: dict[str, Any] | None) -> str:
    lines = [
        f"Тикет: {ticket.get('id')}",
        f"Тема: {ticket.get('subject')}",
        f"Статус: {ticket.get('status')}",
        f"Приоритет: {ticket.get('priority')}",
        f"Создан: {ticket.get('created_at')}",
        f"Обновлён: {ticket.get('updated_at')}",
        f"Пользователь: {user.get('name') if user else ticket.get('user_id')}",
        f"Описание: {ticket.get('description')}",
    ]
    messages = ticket.get("messages") or []
    if messages:
        lines.append("Переписка:")
        for message in messages:
            lines.append(
                f"  [{message.get('at')}] {message.get('author')}: {message.get('text')}"
            )
    return "\n".join(lines)


@mcp.tool()
def get_ticket(ticket_id: str) -> str:
    """Возвращает тикет поддержки вместе с данными пользователя.

    Args:
        ticket_id: Идентификатор тикета (например, 'T-1001').
    """
    ticket = next(
        (t for t in _tickets() if str(t.get("id")) == str(ticket_id)), None
    )
    if ticket is None:
        return f"Тикет '{ticket_id}' не найден."
    user = _find_user_by_id(ticket.get("user_id", ""))
    return _format_ticket(ticket, user)


@mcp.tool()
def find_user(identifier: str) -> str:
    """Ищет пользователя по ID, email или части имени.

    Args:
        identifier: ID, email или фрагмент имени пользователя.
    """
    needle = identifier.strip().lower()
    if not needle:
        return "Ошибка: пустой идентификатор."

    for user in _users():
        haystack = " ".join(
            str(user.get(field, "")) for field in ("id", "email", "name")
        ).lower()
        if needle in haystack:
            return _format_user(user)
    return f"Пользователь '{identifier}' не найден."


@mcp.tool()
def list_tickets(status: str = "", user_id: str = "") -> str:
    """Показывает список тикетов с фильтрами.

    Args:
        status: Фильтр по статусу, например 'open' (необязательно).
        user_id: Фильтр по ID пользователя (необязательно).
    """
    tickets = _tickets()
    if status:
        tickets = [
            t for t in tickets if str(t.get("status")).lower() == status.lower()
        ]
    if user_id:
        tickets = [t for t in tickets if str(t.get("user_id")) == str(user_id)]

    if not tickets:
        return "Тикеты не найдены."
    lines = []
    for ticket in tickets:
        lines.append(
            f"- {ticket.get('id')} | {ticket.get('status')} | "
            f"{ticket.get('priority')} | {ticket.get('subject')} "
            f"(пользователь: {ticket.get('user_id')})"
        )
    return f"Найдено тикетов: {len(tickets)}\n" + "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
