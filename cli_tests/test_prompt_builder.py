"""Регрессионные тесты PromptBuilder и стратегий управления окном.

Проверяют инварианты централизованной сборки контекста, которые легко
сломать при рефакторинге:
- ровно один базовый system-блок;
- реальные переводы строк (а не литеральные "\\n");
- память, профиль задачи и фаза не теряются, в том числе при суммаризации;
- стратегии не разрывают группы tool-вызовов.
"""

import os
import sys
from pathlib import Path

os.environ["APPLICATION_MODE"] = "TEST"
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Prompt, TaskProfile
from context_strategies import (
    KeyValueMemoryStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
    create_strategy_from_dict,
)
from llm_providers import LlmResponse
from prompt_builder import PromptBuilder, PromptSources
from rag_models import RagContextChunk


class _StubLlmProvider:
    """Провайдер-заглушка, всегда возвращающий фиксированное саммари."""

    def generate(self, messages, **kwargs):
        return LlmResponse(
            content="SUMMARY",
            prompt_tokens=11,
            completion_tokens=7,
        )


def _history(n_messages: int) -> list[Prompt]:
    history = [Prompt(role="system", content="Persona")]
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        history.append(Prompt(role=role, content=f"msg-{i}"))
    return history


def _task_profile(**kwargs) -> TaskProfile:
    defaults = {
        "id": "p1",
        "name": "Profile",
        "description": "desc",
        "created_at": None,
    }
    defaults.update(kwargs)
    return TaskProfile(**defaults)


def test_single_system_block_and_real_newlines():
    sources = PromptSources(
        global_facts=["fact-a"],
        task_profile=_task_profile(
            facts=["task-fact"],
            preferences="prefer",
            invariants=["rule-1"],
        ),
        phase_description="Фаза: PLAN",
    )

    prepared = PromptBuilder().build(_history(2), sources, SlidingWindowStrategy(10))

    system_messages = [m for m in prepared.messages if m["role"] == "system"]
    assert len(system_messages) == 1
    content = system_messages[0]["content"]
    assert "\\n" not in content
    assert "Persona" in content
    assert "Память о пользователе:" in content
    assert "fact-a" in content
    assert "Память задачи (Profile):" in content
    assert "Предпочтения задачи (Profile):" in content
    assert "ИНВАРИАНТЫ ЗАДАЧИ (Profile)" in content
    assert "Фаза: PLAN" in content


def test_persona_fallback_when_no_system_prompt():
    history = [Prompt(role="user", content="hi")]
    sources = PromptSources(phase_description="Фаза: PLAN")

    prepared = PromptBuilder().build(history, sources, SlidingWindowStrategy(10))

    system_messages = [m for m in prepared.messages if m["role"] == "system"]
    assert len(system_messages) == 1
    assert system_messages[0]["content"].startswith("Ты полезный ассистент.")


def test_context_sources_survive_summarization():
    sources = PromptSources(
        global_facts=["global-fact"],
        task_profile=_task_profile(facts=["task-fact"], invariants=["rule-1"]),
        phase_description="Фаза: EXECUTE",
    )
    strategy = SummarizationStrategy(non_compressible_count=1, buffer_size=1)

    prepared = PromptBuilder().build(
        _history(5), sources, strategy, _StubLlmProvider()
    )

    assert prepared.summary == "SUMMARY"
    assert prepared.summarization_tokens == (11, 7)
    assert any(
        m["role"] == "system" and "История диалога: SUMMARY" in m["content"]
        for m in prepared.messages
    )
    base_system = next(m for m in prepared.messages if m["role"] == "system")
    assert "global-fact" in base_system["content"]
    assert "task-fact" in base_system["content"]
    assert "rule-1" in base_system["content"]
    assert "Фаза: EXECUTE" in base_system["content"]


def test_rag_context_injected_into_system_prompt():
    sources = PromptSources(
        phase_description="Фаза: PLAN",
        rag_context=[
            RagContextChunk(
                chunk_id=1,
                document_id=1,
                knowledge_base_id=1,
                document_name="doc.txt",
                chunk_index=2,
                text="Уникальный факт RAG",
                vector_distance=0.1,
            )
        ],
    )

    prepared = PromptBuilder().build(_history(2), sources, SlidingWindowStrategy(10))

    content = prepared.messages[0]["content"]
    assert "--- КОНТЕКСТ ИЗ БАЗ ЗНАНИЙ ---" in content
    assert "doc.txt" in content
    assert "фрагмент 3" in content
    assert "Уникальный факт RAG" in content


def test_no_rag_section_without_context():
    prepared = PromptBuilder().build(
        _history(2), PromptSources(), SlidingWindowStrategy(10)
    )

    assert "КОНТЕКСТ ИЗ БАЗ ЗНАНИЙ" not in prepared.messages[0]["content"]


def test_key_value_strategy_serialization_roundtrip():
    strategy = KeyValueMemoryStrategy(non_compressible_count=2, buffer_size=3)
    strategy.summary = '{"цель": "X"}'

    restored = create_strategy_from_dict(strategy.to_dict())

    assert isinstance(restored, KeyValueMemoryStrategy)
    assert restored.summary == '{"цель": "X"}'
    assert restored.non_compressible_count == 2
    assert restored.buffer_size == 3


def test_sliding_window_does_not_split_tool_group():
    tool_calls = Prompt(
        role="assistant",
        content="",
        tool_calls=[
            type(
                "TC",
                (),
                {"id": "t1", "name": "n", "arguments": "{}"},
            )()
        ],
    )
    dialogue = [
        Prompt(role="user", content="msg-0"),
        Prompt(role="assistant", content="msg-1"),
        tool_calls,
        Prompt(role="tool", content="result", tool_call_id="t1", name="n"),
        Prompt(role="assistant", content="msg-4"),
        Prompt(role="user", content="msg-5"),
    ]

    # Наивный срез [3:] начинался бы с осиротевшего tool-ответа.
    result = SlidingWindowStrategy(3).apply(dialogue)

    roles = [m.role for m in result.dialogue]
    assert "tool" not in roles
    assert roles == ["assistant", "user"]
