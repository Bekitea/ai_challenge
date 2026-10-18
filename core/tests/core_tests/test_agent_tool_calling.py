"""Регрессионный unit-тест многораундового tool calling.

Проверяет, что на каждой следующей итерации запроса к LLM присутствуют ВСЕ
предыдущие tool-вызовы и их результаты. Раньше отправлялся только протокол
текущего раунда, из-за чего модель «теряла» результаты предыдущих шагов
(критично для цепочек поиск → чтение → запись по нескольким файлам).
"""

import os

os.environ["APPLICATION_MODE"] = "TEST"

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.tool_call import ToolCall
from core.domain.entities.agent import Agent


class _Repo:
    def get_global_memory(self):
        return GlobalMemory()

    def get_task_memory(self, conversation_id):
        return None

    def update_agent(self, agent):
        pass


class _RecordingProvider:
    """Отдаёт заранее заданные ответы и запоминает отправленные сообщения."""

    provider_name = "recording"

    def __init__(self, responses):
        self._responses = list(responses)
        self.sent: list[list[dict]] = []

    def list_models(self):
        return []

    def generate(self, messages, **kwargs):
        self.sent.append(list(messages))
        return self._responses.pop(0)


class _Executor:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, call):
        self.calls.append(call.name)
        return f"result:{call.name}"


def _agent() -> Agent:
    return Agent(
        agent_id=1,
        name="Test",
        conversation_id="conv-1",
        initial_settings=AgentSettings(model_id="m", provider="stub"),
        messages=[],
    )


def test_previous_tool_rounds_are_visible_on_followup_requests():
    provider = _RecordingProvider(
        [
            LlmResponse(
                content="",
                tool_calls=[ToolCall(id="a", name="files__read_file", arguments="{}")],
            ),
            LlmResponse(
                content="",
                tool_calls=[
                    ToolCall(id="b", name="files__search_in_files", arguments="{}")
                ],
            ),
            LlmResponse(content="готово", prompt_tokens=10, completion_tokens=5),
        ]
    )
    executor = _Executor()

    response = _agent().continue_dialog(
        "найди и прочитай",
        repository=_Repo(),
        llm_provider=provider,
        tool_executor=executor,
    )

    assert response.content == "готово"
    assert executor.calls == ["files__read_file", "files__search_in_files"]

    # Второй запрос видит результат первого раунда.
    second = provider.sent[1]
    assert any(msg.get("tool_call_id") == "a" for msg in second)
    assert any(msg.get("content") == "result:files__read_file" for msg in second)

    # Третий запрос видит оба предыдущих раунда.
    third = provider.sent[2]
    assert any(msg.get("tool_call_id") == "a" for msg in third)
    assert any(msg.get("tool_call_id") == "b" for msg in third)
    assert any(msg.get("content") == "result:files__read_file" for msg in third)
    assert any(msg.get("content") == "result:files__search_in_files" for msg in third)
