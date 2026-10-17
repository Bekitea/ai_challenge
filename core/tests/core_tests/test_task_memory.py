"""Тесты памяти задачи диалога: хранилище, обновление и промпт.

Проверяют чистую логику без сети: файловый репозиторий, перекрывающую
семантику ``Agent.update_task_memory`` и подмешивание секции в системный
промпт через ``PromptBuilder``. Персистентность памяти идёт через репозиторий
агента, который передаётся в методы (fail-fast без него).
"""

import os

os.environ["APPLICATION_MODE"] = "TEST"

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.prompt import Prompt
from core.domain.dtos.prompt_sources import PromptSources
from core.domain.dtos.task_memory import TaskMemory
from core.domain.entities.agent import Agent
from core.domain.entities.prompt_builder import PromptBuilder
from core.domain.entities.sliding_window_strategy import SlidingWindowStrategy
from core.infrastructure.persistence.file_task_memory_repository import (
    FileTaskMemoryRepository,
)


class _StubLlmProvider:
    def __init__(self, content: str):
        self.content = content
        self.json_calls = 0
        self.last_model_id = None

    def generate(self, messages, **kwargs):
        if kwargs.get("response_format"):
            self.json_calls += 1
        self.last_model_id = kwargs.get("model_id")
        return LlmResponse(content=self.content, prompt_tokens=5, completion_tokens=3)


class _JsonAwareProvider:
    """Провайдер, отвечающий разным JSON на память задачи и на факты."""

    def __init__(self, task_json: str, facts_json: str):
        self.task_json = task_json
        self.facts_json = facts_json

    def generate(self, messages, **kwargs):
        system = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "system"
        ).lower()
        content = (
            self.task_json
            if "память задачи диалога" in system
            else self.facts_json
        )
        return LlmResponse(content=content, prompt_tokens=1, completion_tokens=1)


class _FakeAgentRepository:
    """Минимальный репозиторий агента для unit-тестов памяти."""

    def __init__(self, tmp_path):
        self._global_memory = GlobalMemory()
        self._task_memory = FileTaskMemoryRepository(str(tmp_path))
        self.updated_agents = []

    def get_global_memory(self):
        return self._global_memory

    def save_global_memory(self, memory):
        self._global_memory = memory

    def get_task_memory(self, conversation_id):
        return self._task_memory.get_memory(conversation_id)

    def save_task_memory(self, conversation_id, memory):
        self._task_memory.save_memory(conversation_id, memory)

    def delete_task_memory(self, conversation_id):
        self._task_memory.delete_memory(conversation_id)

    def save_task_profile_facts(self, profile_id, facts):
        pass

    def update_agent(self, agent):
        self.updated_agents.append(agent)


def _make_agent(repository, conversation_id="conv-1"):
    return Agent(
        agent_id=1,
        name="Test",
        conversation_id=conversation_id,
        initial_settings=AgentSettings(model_id="test-model", provider="yandex"),
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
    repository = _FakeAgentRepository(tmp_path)
    agent = _make_agent(repository)
    provider = _StubLlmProvider(
        '{"goal": "первая цель", "constraints": ["old"], "terms": [], '
        '"clarifications": []}'
    )

    agent.update_task_memory(repository=repository, llm_provider=provider)
    assert agent.task_memory.goal == "первая цель"
    assert agent.task_memory.constraints == ["old"]
    # Служебный запрос обязан использовать модель чата, иначе провайдер
    # с обязательным model_id упадёт (регрессия пустого model_id).
    assert provider.last_model_id == "test-model"

    provider.content = (
        '{"goal": "новая цель", "constraints": ["new"], '
        '"terms": ["RAG — поиск"], "clarifications": ["решено: локально"]}'
    )
    agent.update_task_memory(repository=repository, llm_provider=provider)

    assert agent.task_memory.goal == "новая цель"
    assert agent.task_memory.constraints == ["new"]
    assert agent.task_memory.terms == ["RAG — поиск"]
    assert agent.task_memory.clarifications == ["решено: локально"]


def test_update_task_memory_preserves_missing_fields(tmp_path):
    repository = _FakeAgentRepository(tmp_path)
    agent = _make_agent(repository)
    provider = _StubLlmProvider(
        '{"goal": "цель", "constraints": ["keep"], "terms": ["T"], '
        '"clarifications": ["C"]}'
    )
    agent.update_task_memory(repository=repository, llm_provider=provider)

    provider.content = '{"goal": "обновлённая цель"}'
    agent.update_task_memory(repository=repository, llm_provider=provider)

    assert agent.task_memory.goal == "обновлённая цель"
    assert agent.task_memory.constraints == ["keep"]
    assert agent.task_memory.terms == ["T"]
    assert agent.task_memory.clarifications == ["C"]


def test_task_memory_persisted_across_agents(tmp_path):
    repository = _FakeAgentRepository(tmp_path)
    agent = _make_agent(repository)
    provider = _StubLlmProvider(
        '{"goal": "цель", "constraints": [], "terms": [], '
        '"clarifications": []}'
    )
    agent.update_task_memory(repository=repository, llm_provider=provider)

    reloaded = _make_agent(repository)
    reloaded.refresh_memory(repository)

    assert reloaded.task_memory.goal == "цель"


def test_branch_does_not_copy_task_memory(tmp_path):
    repository = _FakeAgentRepository(tmp_path)
    agent = _make_agent(repository)
    provider = _StubLlmProvider(
        '{"goal": "цель", "constraints": [], "terms": [], '
        '"clarifications": []}'
    )
    agent.update_task_memory(repository=repository, llm_provider=provider)
    assert not agent.task_memory.is_empty()

    branched = agent.branch(new_name="branch", repository=repository)

    assert branched.conversation_id != agent.conversation_id
    assert branched.task_memory.is_empty()


def test_branch_derives_own_task_memory_on_flush(tmp_path):
    """Ветка извлекает свою память задачи из скопированной истории.

    Сразу после ``branch`` память пуста, но финальный flush на выходе
    (``save_memory``) извлекает память из копии диалога под собственным
    ``conversation_id`` и не затрагивает родителя.
    """
    repository = _FakeAgentRepository(tmp_path)
    agent = _make_agent(repository)
    provider = _StubLlmProvider(
        '{"goal": "цель из копии", "constraints": ["из копии"], '
        '"terms": [], "clarifications": []}'
    )

    branched = agent.branch(new_name="branch", repository=repository)
    assert branched.task_memory.is_empty()

    branched.save_memory(repository=repository, llm_provider=provider)

    assert branched.task_memory.goal == "цель из копии"
    stored = repository.get_task_memory(branched.conversation_id)
    assert stored is not None
    assert stored.goal == "цель из копии"

    # Родитель не затронут: у него нет сохранённой памяти задачи.
    assert agent.task_memory.is_empty()
    assert repository.get_task_memory(agent.conversation_id) is None


def test_save_memory_preserves_previously_stored_global_facts(tmp_path):
    """Регресс: сохранение памяти не должно затирать ранее накопленные факты.

    ``Agent.save_memory`` обязан поднять актуальную память из репозитория
    перед merge; иначе старые факты теряются при перезаписи.
    """
    repository = _FakeAgentRepository(tmp_path)
    repository.save_global_memory(GlobalMemory(facts=["старый факт"]))

    agent = _make_agent(repository)
    provider = _JsonAwareProvider(
        task_json=(
            '{"goal": "", "constraints": [], "terms": [], "clarifications": []}'
        ),
        facts_json='{"facts": ["новый факт"]}',
    )

    agent.save_memory(repository=repository, llm_provider=provider)

    stored = repository.get_global_memory().facts
    assert "старый факт" in stored
    assert "новый факт" in stored


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
