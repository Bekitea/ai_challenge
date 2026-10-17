"""Регрессионные тесты OllamaLlmProvider.

Проверяют, что параметры корректно транслируются в OpenAI-совместимый запрос
Ollama. Ключевой инвариант: ``reasoning_effort`` должен доходить до API, иначе
thinking-модели (например, Granite) продолжают рассуждать даже при значении
``"none"``.
"""

import os
from types import SimpleNamespace

os.environ["APPLICATION_MODE"] = "TEST"

from core.infrastructure.llm.ollama_llm_provider import OllamaLlmProvider


class _RecordingCompletions:
    """Заглушка ``client.chat.completions``, запоминающая переданные kwargs."""

    def __init__(self):
        self.captured_kwargs: dict | None = None

    def create(self, **kwargs):
        self.captured_kwargs = kwargs
        message = SimpleNamespace(
            content="ok", reasoning_content=None, tool_calls=None
        )
        choice = SimpleNamespace(message=message)
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=1)
        return SimpleNamespace(choices=[choice], usage=usage)


def _make_provider() -> tuple[OllamaLlmProvider, _RecordingCompletions]:
    provider = OllamaLlmProvider()
    completions = _RecordingCompletions()
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return provider, completions


def test_ollama_forwards_reasoning_effort():
    provider, completions = _make_provider()
    provider.generate(
        messages=[{"role": "user", "content": "hi"}],
        model_id="granite4.2:3b-q4_K_M",
        reasoning_effort="none",
    )
    assert completions.captured_kwargs["reasoning_effort"] == "none"


def test_ollama_omits_reasoning_effort_when_not_set():
    provider, completions = _make_provider()
    provider.generate(
        messages=[{"role": "user", "content": "hi"}],
        model_id="granite4.2:3b-q4_K_M",
    )
    assert "reasoning_effort" not in completions.captured_kwargs


def test_ollama_still_ignores_top_k():
    provider, completions = _make_provider()
    provider.generate(
        messages=[{"role": "user", "content": "hi"}],
        model_id="granite4.2:3b-q4_K_M",
        top_k=40,
    )
    assert "top_k" not in completions.captured_kwargs
