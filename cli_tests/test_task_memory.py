"""Тесты памяти задачи диалога: хранилище, обновление и промпт.

Проверяют чистую логику без сети: файловый репозиторий, перекрывающую
семантику ``Agent.update_task_memory`` и подмешивание секции в системный
промпт через ``PromptBuilder``.
"""

import os
import sys
from pathlib import Path

os.environ["APPLICATION_MODE"] = "TEST"
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import Agent, GlobalMemory, Prompt, TaskMemory
from context_strategies import SlidingWindowStrategy
from llm_providers import LlmResponse
from prompt_builder import PromptBuilder, PromptSources
from storage.task_memory_repository import FileTaskMemoryRepository


class _StubLlmProvider:
    def __init__(self, content: str):
        self.content = content
        self.json_calls = 0

    def generate(self, messages, **kwargs):
        if kwargs.get("response_format"):
            self.json_calls += 1
        return LlmResponse(content=self.content, prompt_tokens=5, completion_tokens=3)


class _FakeGlobalMemoryRepository:
    def __init__(self):
        self._memory = GlobalMemory()

    def get_memory(self):
        return self._memory

    def save_memory(self, memory):
        self._memory = memory


class _Dummy:
    pass


def _make_agent(tmp_path, llm_content, conversation_id="conv-1"):
    return Agent(
        agent_id=1,
        conversation_id=conversation_id,
        name="Test",
        llm_provider=_StubLlmProvider(llm_content),
        history_storage=_Dummy(),
        global_memory_repository=_FakeGlobalMemoryRepository(),
        task_profile_repository=_Dummy(),
        task_memory_repository=FileTaskMemoryRepository(str(tmp_path)),
        messages=[Prompt(role="user", content="привет")],
    )


def test_repository_roundtrip_and_delete(tmp_path):
    repo = FileTaskMemoryRepository(str(tmp_path))
    assert repo.get_memory("c1") is None

    memory = TaskMemory(goal="цель", constraints=["A"], terms=["T — t"])
    repo.save_memory("c1", memory)

    loaded = repo.get_memory("c1")
    assert loaded is not None
    assert loaded.goal == "цель"
    assert loaded.constraints == ["A"]
    assert loaded.terms == ["T — t"]

    repo.delete_memory("c1")
    assert repo.get_memory("c1") is None


def test_update_task_memory_replaces_old_values(tmp_path):
    agent = _make_agent(
        tmp_path,
        '{"goal": "первая цель", "constraints": ["old"], "terms": [], '
        '"clarifications": []}',
    )
    agent.update_task_memory()
    assert agent.task_memory.goal == "первая цель"
    assert agent.task_memory.constraints == ["old"]

    agent._llm_provider.content = (
        '{"goal": "новая цель", "constraints": ["new"], '
        '"terms": ["RAG — поиск"], "clarifications": ["решено: локально"]}'
    )
    agent.update_task_memory()

    assert agent.task_memory.goal == "новая цель"
    assert agent.task_memory.constraints == ["new"]
    assert agent.task_memory.terms == ["RAG — поиск"]
    assert agent.task_memory.clarifications == ["решено: локально"]


def test_update_task_memory_preserves_missing_fields(tmp_path):
    agent = _make_agent(
        tmp_path,
        '{"goal": "цель", "constraints": ["keep"], "terms": ["T"], '
        '"clarifications": ["C"]}',
    )
    agent.update_task_memory()

    agent._llm_provider.content = '{"goal": "обновлённая цель"}'
    agent.update_task_memory()

    assert agent.task_memory.goal == "обновлённая цель"
    assert agent.task_memory.constraints == ["keep"]
    assert agent.task_memory.terms == ["T"]
    assert agent.task_memory.clarifications == ["C"]


def test_task_memory_persisted_across_agents(tmp_path):
    agent = _make_agent(
        tmp_path,
        '{"goal": "цель", "constraints": [], "terms": [], '
        '"clarifications": []}',
    )
    agent.update_task_memory()

    reloaded = Agent(
        agent_id=1,
        conversation_id="conv-1",
        name="Test",
        llm_provider=_StubLlmProvider("{}"),
        history_storage=_Dummy(),
        global_memory_repository=_FakeGlobalMemoryRepository(),
        task_profile_repository=_Dummy(),
        task_memory_repository=FileTaskMemoryRepository(str(tmp_path)),
    )
    assert reloaded.task_memory.goal == "цель"


def test_branch_does_not_copy_task_memory(tmp_path):
    agent = _make_agent(
        tmp_path,
        '{"goal": "цель", "constraints": [], "terms": [], '
        '"clarifications": []}',
    )
    agent.update_task_memory()
    assert not agent.task_memory.is_empty()

    branched = agent.branch(new_name="branch")

    assert branched.conversation_id != agent.conversation_id
    assert branched.task_memory.is_empty()


def test_task_memory_section_in_prompt():
    sources = PromptSources(
        task_memory=TaskMemory(
            goal="Цель X",
            constraints=["Ограничение 1"],
            terms=["Термин — значение"],
            clarifications=["Уточнение 1"],
        )
    )
    prepared = PromptBuilder().build(
        [Prompt(role="system", content="Persona")],
        sources,
        SlidingWindowStrategy(10),
    )
    content = prepared.messages[0]["content"]
    assert "--- ПАМЯТЬ ЗАДАЧИ ---" in content
    assert "Цель: Цель X" in content
    assert "Ограничение 1" in content
    assert "Термин — значение" in content
    assert "Уточнение 1" in content
    assert "не противоречь" in content


def test_empty_task_memory_not_in_prompt():
    prepared = PromptBuilder().build(
        [Prompt(role="system", content="Persona")],
        PromptSources(task_memory=TaskMemory()),
        SlidingWindowStrategy(10),
    )
    assert "ПАМЯТЬ ЗАДАЧИ" not in prepared.messages[0]["content"]
