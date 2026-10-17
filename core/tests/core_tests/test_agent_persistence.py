"""Unit-тесты fail-fast поведения домена агента.

Проверяют, что при отсутствии репозитория (или conversation_id) методы,
работающие с памятью и историей, падают с доменным исключением
``AgentPersistenceError``, а не деградируют молча. Также проверяется, что
ошибки доступа к памяти/истории оборачиваются в соответствующие доменные
исключения.
"""

import os

import pytest

os.environ["APPLICATION_MODE"] = "TEST"

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.prompt import Prompt
from core.domain.dtos.task_memory import TaskMemory
from core.domain.entities.agent import Agent
from core.domain.entities.agent_phase import AgentPhase
from core.domain.exceptions.agent_persistence_error import AgentPersistenceError
from core.domain.exceptions.history_access_error import HistoryAccessError
from core.domain.exceptions.memory_access_error import MemoryAccessError


class _StubProvider:
    provider_name = "stub"

    def generate(self, messages, **kwargs):
        return LlmResponse(content="ok", prompt_tokens=1, completion_tokens=1)

    def list_models(self):
        return []


class _BreakyRepository:
    """Репозиторий, у которого доступ к памяти/истории падает."""

    def __init__(self, *, memory_broken=False, save_broken=False):
        self._memory_broken = memory_broken
        self._save_broken = save_broken

    def get_global_memory(self):
        if self._memory_broken:
            raise RuntimeError("storage unavailable")
        return GlobalMemory()

    def save_global_memory(self, memory):
        if self._memory_broken:
            raise RuntimeError("storage unavailable")

    def get_task_memory(self, conversation_id):
        if self._memory_broken:
            raise RuntimeError("storage unavailable")

    def save_task_memory(self, conversation_id, memory):
        if self._memory_broken:
            raise RuntimeError("storage unavailable")

    def save_task_profile_facts(self, profile_id, facts):
        if self._memory_broken:
            raise RuntimeError("storage unavailable")

    def update_agent(self, agent):
        if self._save_broken:
            raise RuntimeError("db unavailable")


def _agent(conversation_id="conv-1") -> Agent:
    return Agent(
        agent_id=1,
        name="Test",
        conversation_id=conversation_id,
        initial_settings=AgentSettings(model_id="m", provider="stub"),
        messages=[Prompt(role="user", content="привет")],
    )


def test_save_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().save(None)


def test_refresh_memory_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().refresh_memory(None)


def test_update_settings_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().update_settings(AgentSettings(), None)


def test_set_phase_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().set_phase(AgentPhase.EXECUTE, None)


def test_handle_phase_command_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().handle_phase_command("/execute", None)


def test_branch_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().branch(new_name="b", repository=None)


def test_attach_mcp_server_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().attach_mcp_server("time", None)


def test_continue_dialog_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().continue_dialog(
            "привет", repository=None, llm_provider=_StubProvider()
        )


def test_update_task_memory_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().update_task_memory(
            repository=None, llm_provider=_StubProvider()
        )


def test_save_memory_without_repository_raises():
    with pytest.raises(AgentPersistenceError):
        _agent().save_memory(repository=None, llm_provider=_StubProvider())


def test_missing_conversation_id_raises_on_memory_access():
    with pytest.raises(AgentPersistenceError):
        _agent(conversation_id=None).refresh_memory(_BreakyRepository())


def test_memory_access_error_wrapped():
    with pytest.raises(MemoryAccessError):
        _agent().refresh_memory(_BreakyRepository(memory_broken=True))


def test_history_access_error_wrapped():
    with pytest.raises(HistoryAccessError):
        _agent().save(_BreakyRepository(save_broken=True))


def test_memory_access_error_is_persistence_error():
    assert issubclass(MemoryAccessError, AgentPersistenceError)
    assert issubclass(HistoryAccessError, AgentPersistenceError)


def test_refresh_memory_loads_task_memory():
    class _Repo:
        def get_global_memory(self):
            return GlobalMemory(facts=["f"])

        def get_task_memory(self, conversation_id):
            return TaskMemory(goal="цель")

    agent = _agent()
    agent.refresh_memory(_Repo())

    assert agent.global_memory.facts == ["f"]
    assert agent.task_memory.goal == "цель"
