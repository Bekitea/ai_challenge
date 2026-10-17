from __future__ import annotations

from typing import Any

from core.domain.dtos.prompt import Prompt


def prompt_to_llm_dict(msg: Prompt) -> dict[str, Any]:
    """Конвертирует объект Prompt в сообщение OpenAI-совместимого формата.

    Сохраняет протокольные поля tool calling: у assistant-сообщений —
    tool_calls, у role="tool" — tool_call_id и name. Без этого история с
    вызовами инструментов становится невалидной для API (400 "missing field
    tool_call_id"), а стратегии контекстного окна теряют протокол при
    подготовке сообщений.
    """
    entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
    tool_calls = getattr(msg, "tool_calls", None)
    if msg.role == "assistant" and tool_calls:
        entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in tool_calls
        ]
    elif msg.role == "tool":
        tool_call_id = getattr(msg, "tool_call_id", None)
        if tool_call_id is not None:
            entry["tool_call_id"] = tool_call_id
        name = getattr(msg, "name", None)
        if name is not None:
            entry["name"] = name
    return entry


def group_tool_blocks(messages: list[Prompt]) -> list[list[Prompt]]:
    """Группирует сообщения так, чтобы группы assistant(tool_calls) + их
    tool-ответы оставались неделимыми.

    Это нужно стратегиям (скользящее окно, суммаризация), чтобы никогда не
    отрывать tool-ответы от соответствующего assistant-сообщения с tool_calls
    — иначе LLM получает невалидный протокол и отвечает ошибкой 400.
    """
    groups: list[list[Prompt]] = []
    current: list[Prompt] | None = None
    for msg in messages:
        if getattr(msg, "tool_calls", None):
            if current is not None:
                groups.append(current)
            current = [msg]
        elif msg.role == "tool" and current is not None:
            current.append(msg)
        else:
            if current is not None:
                groups.append(current)
                current = None
            groups.append([msg])
    if current is not None:
        groups.append(current)
    return groups


def align_group_boundary(groups: list[list[Prompt]], index: int) -> int:
    """Сдвигает границу среза назад на целую группу сообщений.

    Используется стратегиями: срез dialogue[:index] должен заканчиваться
    целиком на границе группы, чтобы assistant(tool_calls) не уходил в
    саммари, а его tool-ответы — в «хвост» (и наоборот).
    """
    remainder = 0
    for g in groups[index:]:
        remainder += len(g)
    return (
        max(0, min(index, len(groups) - 1))
        if not groups
        else _align_impl(groups, index, remainder)
    )


def _align_impl(groups: list[list[Prompt]], index: int, remainder: int) -> int:
    while index > 0 and remainder < len(groups[index - 1]):
        remainder += len(groups[index - 1])
        index -= 1
    return index


def align_window_start(messages: list[Prompt], offset: int) -> int:
    """Возвращает индекс начала окна, выровненный по целым группам.

    ``offset`` — желаемый индекс начала среза (len(messages) - window_size).
    Если внутри группы, граница сдвигается назад к началу группы.
    """
    if offset <= 0:
        return 0
    groups = group_tool_blocks(messages)
    aligned = 0
    for group in groups:
        if aligned >= offset:
            break
        aligned += len(group)
    return aligned


def sanitize_llm_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Приводит список сообщений к валидному протоколу tool calling.

    Убирает из запроса к LLM сообщения, которые ломают десериализацию на
    стороне API (например, YandexGPT возвращает 400 "missing field
    tool_call_id"):
      - assistant-сообщения с tool_calls, для которых не все tool-ответы
        присутствуют в истории (неполная группа — например, процесс был
        прерван между записью assistant и tool-сообщений);
      - tool-сообщения без корректной пары к assistant с tool_calls;
      - tool-вызовы, идущие раньше первого сообщения пользователя.
    """
    result: list[dict[str, Any]] = []
    i = 0
    n = len(messages)

    def has_user_before(start: int) -> bool:
        for m in messages[:start]:
            if m.get("role") == "user":
                return True
        return False

    while i < n:
        msg = messages[i]
        tool_calls = msg.get("tool_calls")
        if msg.get("role") == "assistant" and tool_calls:
            required = {tc.get("id") for tc in tool_calls}
            j = i + 1
            responses: list[dict[str, Any]] = []
            while j < n and messages[j].get("role") == "tool":
                responses.append(messages[j])
                j += 1
            responded = {r.get("tool_call_id") for r in responses}
            if required and required == responded and has_user_before(i):
                result.append(msg)
                result.extend(responses)
            else:
                # Неполная/некорректная группа — отбрасываем её целиком,
                # сохранив текстовый контент assistant как обычное сообщение.
                content = msg.get("content")
                if content and has_user_before(i):
                    result.append({"role": "assistant", "content": content})
            i = j
            continue
        if msg.get("role") == "tool":
            # Осиротевший tool-ответ (без предшествующего assistant с
            # tool_calls) — в запрос отправлять нельзя.
            i += 1
            continue
        result.append(msg)
        i += 1
    return result
