"""Unit-тесты разбора текстовых tool-вызовов и wiring в парсер ответа."""

import os
from types import SimpleNamespace

os.environ["APPLICATION_MODE"] = "TEST"

from core.infrastructure.llm.openai_response_parser import _parse_openai_response
from core.infrastructure.llm.text_tool_calls import (
    extract_text_tool_calls,
    strip_text_tool_calls,
)


def test_bracket_format_is_parsed():
    content = (
        "[TOOL_CALL_START]files__write_file\n"
        '{"apply": false, "content": "hi"}\n'
        "[TOOL_CALL_END]"
    )

    calls = extract_text_tool_calls(content)

    assert len(calls) == 1
    assert calls[0].name == "files__write_file"
    assert calls[0].arguments == {"apply": False, "content": "hi"}


def test_bracket_format_without_end_marker():
    content = '[TOOL_CALL_START]files__read_file\n{"path": "README.md"}'

    calls = extract_text_tool_calls(content)

    assert len(calls) == 1
    assert calls[0].name == "files__read_file"
    assert calls[0].arguments == {"path": "README.md"}


def test_multiple_bracket_calls():
    content = (
        "[TOOL_CALL_START]files__read_file\n{\"path\": \"a.py\"}\n"
        "[TOOL_CALL_END]"
        "[TOOL_CALL_START]files__read_file\n{\"path\": \"b.py\"}\n"
        "[TOOL_CALL_END]"
    )

    calls = extract_text_tool_calls(content)

    assert [c.arguments["path"] for c in calls] == ["a.py", "b.py"]


def test_xml_format_is_parsed():
    content = '<tool_call>{"name": "files__read_file", "arguments": {"path": "x"}}</tool_call>'

    calls = extract_text_tool_calls(content)

    assert len(calls) == 1
    assert calls[0].name == "files__read_file"
    assert calls[0].arguments == {"path": "x"}


def test_json_envelope_in_fence_is_parsed():
    content = '```json\n{"name": "git__get_status", "arguments": {}}\n```'

    calls = extract_text_tool_calls(content)

    assert len(calls) == 1
    assert calls[0].name == "git__get_status"


def test_plain_text_is_not_a_tool_call():
    assert extract_text_tool_calls("Просто ответ без инструментов.") == []


def test_strip_removes_bracket_block():
    content = (
        "Проверяю файл...\n"
        "[TOOL_CALL_START]files__read_file\n{\"path\": \"a.py\"}\n[TOOL_CALL_END]"
    )

    assert strip_text_tool_calls(content) == "Проверяю файл..."


def test_parse_openai_response_uses_text_tool_calls():
    content = '[TOOL_CALL_START]files__read_file\n{"path": "a.py"}'
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content, tool_calls=None, reasoning_content=None
                )
            )
        ],
        usage=None,
    )

    parsed = _parse_openai_response(response)

    assert parsed.tool_calls is not None
    assert parsed.tool_calls[0].name == "files__read_file"
    assert parsed.tool_calls[0].arguments == {"path": "a.py"}
    assert parsed.content == ""
