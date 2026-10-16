"""Сценарный мок LLM для e2e-тестов.

Позволяет одним и тем же ``MockLlmProvider`` отдавать разные ответы в разных
тестах, не меняя код приложения. Сценарий передаётся из теста через переменную
окружения ``MOCK_LLM_SCENARIO`` (JSON), потому что CLI-тесты запускают
приложение отдельным subprocess'ом и не могут внедрить объект напрямую.

Формат сценария::

    {
      "responses": [
        {"content": "...", "reasoning": "...", "prompt_tokens": 100,
         "completion_tokens": 50, "tool_calls": [{"id": "1", "name": "t",
         "arguments": "{...}"}], "error": "timeout"}
      ],
      "default": {"content": "..."},
      "json_object": {"facts": ["..."]}
    }

``responses`` расходуются по порядку; после исчерпания используется
``default`` (или штатный echo-ответ). ``json_object`` применяется к запросам с
``response_format={"type": "json_object"}`` (извлечение памяти). ``error``
заставляет провайдер бросить исключение.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

ENV_VAR = "MOCK_LLM_SCENARIO"


@dataclass
class MockScenario:
    """Разобранный сценарий мока: очередь ответов + запасные варианты."""

    responses: list[dict] = field(default_factory=list)
    default: dict | None = None
    json_object: dict | None = None
    _index: int = field(default=0, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> MockScenario:
        """Создаёт сценарий из словаря (уже разобранного JSON)."""
        responses = data.get("responses") or []
        if not isinstance(responses, list):
            responses = []
        return cls(
            responses=[r for r in responses if isinstance(r, dict)],
            default=data.get("default") if isinstance(data.get("default"), dict) else None,
            json_object=(
                data.get("json_object")
                if isinstance(data.get("json_object"), dict)
                else None
            ),
        )

    @classmethod
    def from_json(cls, raw: str) -> MockScenario:
        """Создаёт сценарий из JSON-строки."""
        return cls.from_dict(json.loads(raw))

    def next_json_object(self) -> dict | None:
        """Ответ для запросов с ``response_format=json_object`` (если задан)."""
        return self.json_object

    def next_response(self) -> dict | None:
        """Следующий ответ из очереди, иначе ``default``, иначе ``None``."""
        if self._index < len(self.responses):
            item = self.responses[self._index]
            self._index += 1
            return item
        return self.default


def load_scenario_from_env() -> MockScenario | None:
    """Читает сценарий из ``MOCK_LLM_SCENARIO``.

    Returns:
        MockScenario или None, если переменная не задана/невалидна.
    """
    raw = os.environ.get(ENV_VAR)
    if not raw:
        return None
    try:
        return MockScenario.from_json(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
