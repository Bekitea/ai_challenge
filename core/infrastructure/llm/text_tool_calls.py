from __future__ import annotations

import json
import re

from core.domain.dtos.tool_call import ToolCall

# Некоторые модели (в т.ч. за OpenAI-совместимыми эндпоинтами) возвращают
# tool-вызовы не в структурном поле ``message.tool_calls``, а текстом в
# ``content``. Ниже — разбор наиболее распространённых текстовых диалектов,
# чтобы ассистент всё равно выполнил инструмент.
#
# Поддерживаются:
#   [TOOL_CALL_START]<name>
#   {"arg": "..."}
#   [TOOL_CALL_END]
#   <tool_call>{"name": "<name>", "arguments": {...}}</tool_call>
#   ```json
#   {"name": "<name>", "arguments": {...}}
#   ```

_BRACKET_START = "[TOOL_CALL_START]"
_BRACKET_END = "[TOOL_CALL_END]"
_NAME_RE = re.compile(r"\s*([A-Za-z0-9_][A-Za-z0-9_.\-]*)")
_XML_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_JSON_DECODER = json.JSONDecoder()


def _decode_first_json(text: str) -> dict | None:
    """Разбирает первый JSON-объект в строке (или None)."""
    text = text.lstrip()
    if not text:
        return None
    try:
        obj, _ = _JSON_DECODER.raw_decode(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _arguments_from(value: object) -> dict | str:
    if isinstance(value, (dict, str)):
        return value
    return {}


def _extract_bracket_calls(content: str) -> list[tuple[str, dict | str]]:
    calls: list[tuple[str, dict | str]] = []
    idx = 0
    while True:
        start = content.find(_BRACKET_START, idx)
        if start == -1:
            break
        after = start + len(_BRACKET_START)
        match = _NAME_RE.match(content, after)
        if match is None:
            idx = after
            continue
        name = match.group(1)
        json_start = match.end()
        end = content.find(_BRACKET_END, json_start)
        segment = content[json_start:end] if end != -1 else content[json_start:]
        args = _decode_first_json(segment)
        if args is not None:
            calls.append((name, args))
        idx = (end + len(_BRACKET_END)) if end != -1 else len(content)
    return calls


def _extract_xml_calls(content: str) -> list[tuple[str, dict | str]]:
    calls: list[tuple[str, dict | str]] = []
    for raw in _XML_RE.findall(content):
        payload = _decode_first_json(raw)
        if not payload or "name" not in payload:
            continue
        arguments = payload.get("arguments", payload.get("parameters", {}))
        calls.append((str(payload["name"]), _arguments_from(arguments)))
    return calls


def _extract_json_envelope(content: str) -> list[tuple[str, dict | str]]:
    stripped = content.strip()
    fence = _FENCE_RE.fullmatch(stripped)
    candidate = fence.group(1) if fence else stripped
    payload = _decode_first_json(candidate)
    if not payload or "name" not in payload:
        return []
    if "arguments" not in payload and "parameters" not in payload:
        return []
    arguments = payload.get("arguments", payload.get("parameters", {}))
    return [(str(payload["name"]), _arguments_from(arguments))]


def extract_text_tool_calls(content: str) -> list[ToolCall]:
    """Извлекает tool-вызовы из текстового ответа модели.

    Возвращает пустой список, если текст не является tool-вызовом.
    """
    if not content:
        return []

    raw_calls: list[tuple[str, dict | str]] = []
    if _BRACKET_START in content:
        raw_calls = _extract_bracket_calls(content)
    elif "<tool_call>" in content:
        raw_calls = _extract_xml_calls(content)
    else:
        raw_calls = _extract_json_envelope(content)
    if not raw_calls and _BRACKET_START not in content:
        # Иногда обёртка JSON-конверта есть и внутри фенса при bracket-формате.
        raw_calls = _extract_json_envelope(content)

    return [
        ToolCall(id=f"text-call-{index}", name=name, arguments=arguments)
        for index, (name, arguments) in enumerate(raw_calls, start=1)
    ]


def strip_text_tool_calls(content: str) -> str:
    """Убирает текстовые tool-вызовы из ``content`` (для чистого вывода)."""
    if not content:
        return content
    cleaned = content
    if _BRACKET_START in cleaned:
        parts: list[str] = []
        idx = 0
        while True:
            start = cleaned.find(_BRACKET_START, idx)
            if start == -1:
                parts.append(cleaned[idx:])
                break
            parts.append(cleaned[idx:start])
            end = cleaned.find(_BRACKET_END, start)
            idx = (end + len(_BRACKET_END)) if end != -1 else len(cleaned)
        cleaned = "".join(parts).strip()
    if "<tool_call>" in cleaned:
        cleaned = _XML_RE.sub("", cleaned).strip()
    if _BRACKET_START not in content and "<tool_call>" not in content:
        # Контент целиком был JSON-конвертом (возможно, в ```json-фенсе).
        candidate = _FENCE_RE.match(cleaned.strip())
        payload = _decode_first_json(
            candidate.group(1) if candidate else cleaned
        )
        if payload is not None and "name" in payload:
            return ""
    return cleaned
