from __future__ import annotations

from typing import Any

from config import AVAILABLE_EMBEDDING_MODELS
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.tool_call import ToolCall
from core.infrastructure.llm.text_tool_calls import (
    extract_text_tool_calls,
    strip_text_tool_calls,
)


def _openai():
    """Ленивый импорт SDK ``openai``.

    SDK импортируется ~1.9 с и нужен только для реальных сетевых провайдеров.
    В TEST-режиме (mock-провайдеры) он вообще не должен загружаться — иначе
    каждый из сотен e2e-subprocess-запусков платит за него. Поэтому импорт
    выполняется только в момент фактического обращения к API.
    """
    import openai

    return openai


# Базовые имена embedding-моделей Ollama, которые не должны попадать в список
# чат-моделей (это модели для RAG, а не для генерации ответов).
_EMBEDDING_MODEL_NAMES = set(AVAILABLE_EMBEDDING_MODELS)


def _parse_openai_response(response: Any) -> LlmResponse:
    """Разбирает ответ OpenAI-совместимого API в ``LlmResponse``."""
    message = response.choices[0].message
    raw_content = message.content or ""
    reasoning_text = getattr(message, "reasoning_content", None) or getattr(
        message, "reasoning", None
    )

    tool_calls: list[ToolCall] | None = None
    raw_tool_calls = getattr(message, "tool_calls", None)
    if raw_tool_calls:
        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.function
            tool_calls.append(
                ToolCall(id=tc.id or "", name=fn.name, arguments=fn.arguments)
            )
    elif raw_content:
        # Fallback: модель вернула tool-вызов текстом в content.
        text_calls = extract_text_tool_calls(raw_content)
        if text_calls:
            tool_calls = text_calls
            raw_content = strip_text_tool_calls(raw_content)

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    return LlmResponse(
        content=raw_content,
        reasoning=reasoning_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tool_calls=tool_calls,
    )


def _to_yandex_model_id(raw_id: str, folder_id: str) -> str:
    """Приводит id модели из ответа Yandex к нативному виду без ``gpt://folder/``."""
    if raw_id.startswith("gpt://"):
        rest = raw_id[len("gpt://") :]
        if "/" in rest:
            return rest.split("/", 1)[1]
        return rest
    return raw_id
