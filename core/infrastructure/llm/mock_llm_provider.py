from __future__ import annotations

import json

from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.tool_call import ToolCall
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.infrastructure.llm.mock_scenario import (
    MockScenario,
    load_scenario_from_env,
)

# Модели, которые mock-провайдер возвращает в тестовом режиме. Значения —
# пары (model_id, display_name). Списки для yandex и ollama намеренно разные,
# чтобы e2e-тесты могли проверить выбор между провайдерами и подписи в UI.
MOCK_MODELS: dict[str, list[tuple[str, str]]] = {
    "yandex": [
        ("gpt-oss-120b/latest", "GPT OSS 120B"),
        ("qwen3.6-35b-a3b/latest", "Qwen3.6-35B"),
        ("aliceai-llm-flash/latest", "Alice AI LLM Flash"),
    ],
    "ollama": [
        ("llama3.2:latest", "Llama 3.2 (Local)"),
        ("qwen2.5:7b", "Qwen2.5 7B (Local)"),
    ],
}


class MockLlmProvider:
    """Mock-провайдер для тестирования без реального API.

    Возвращает заглушки вместо реальных запросов к LLM. Имеет настраиваемое
    имя провайдера (``yandex``/``ollama``), чтобы в тестах можно было
    проверять выбор между провайдерами.
    """

    def __init__(
        self,
        provider_name: str = "yandex",
        models: list[tuple[str, str]] | None = None,
        scenario: MockScenario | None = None,
    ):
        """Инициализирует mock-провайдер.

        Args:
            provider_name: Ключ провайдера (совпадает с провайдерами прода).
            models: Список пар (model_id, display_name); по умолчанию берётся
                из ``MOCK_MODELS`` для указанного провайдера.
            scenario: Сценарий ответов. Если не задан, читается из переменной
                окружения ``MOCK_LLM_SCENARIO``.
        """
        self.provider_name = provider_name
        self._models = (
            models if models is not None else MOCK_MODELS.get(provider_name, [])
        )
        self._scenario = scenario if scenario is not None else load_scenario_from_env()

    def _response_from_spec(self, spec: dict) -> LlmResponse:
        """Преобразует элемент сценария в ``LlmResponse`` (или бросает ошибку)."""
        error = spec.get("error")
        if error:
            if error == "timeout":
                raise LlmTimeoutError("mock llm timeout")
            raise RuntimeError(f"mock llm error: {error}")

        tool_calls: list[ToolCall] | None = None
        raw_tool_calls = spec.get("tool_calls")
        if raw_tool_calls:
            tool_calls = [
                ToolCall(
                    id=str(tc.get("id", "")),
                    name=str(tc.get("name", "")),
                    arguments=tc.get("arguments", ""),
                )
                for tc in raw_tool_calls
            ]

        return LlmResponse(
            content=spec.get("content", ""),
            reasoning=spec.get("reasoning"),
            prompt_tokens=spec.get("prompt_tokens"),
            completion_tokens=spec.get("completion_tokens"),
            tool_calls=tool_calls,
        )

    def list_models(self) -> list[LlmModelInfo]:
        """Возвращает детерминированный список моделей для тестов."""
        return [
            LlmModelInfo(model_id=model_id, display_name=display_name)
            for model_id, display_name in self._models
        ]

    def generate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: int = 20,
        top_p: float | None = None,
        top_k: float | None = None,
        response_format: dict | None = None,
        reasoning_effort: str | None = None,
        model_id: str | None = None,
        tools: list[dict] | None = None,
        max_retries: int | None = None,
    ) -> LlmResponse:
        """Генерирует mock-ответ для тестирования.

        Args:
            messages: Список сообщений в формате [{"role": "...", "content": "..."}].
            temperature: Температура генерации (игнорируется).
            max_tokens: Максимальное количество токенов (игнорируется).
            timeout: Таймаут запроса (игнорируется).
            top_p: Параметр выборки ядра (игнорируется).
            top_k: Параметр топ-K выборки (игнорируется).
            response_format: Формат ответа (игнорируется).
            reasoning_effort: Уровень усилий рассуждений (игнорируется).
            model_id: Идентификатор модели (игнорируется).
            tools: Список инструментов MCP (игнорируется).
            max_retries: Число повторов SDK (игнорируется).

        Returns:
            LlmResponse: Mock-объект с содержимым ответа.
        """
        system_text = " ".join(
            msg.get("content", "")
            for msg in messages
            if msg.get("role") == "system"
        )

        # Память задачи диалога: возвращаем структурированное состояние,
        # чтобы тесты могли проверить подмешивание в системный промпт.
        if response_format and response_format.get("type") == "json_object":
            if self._scenario is not None:
                spec = self._scenario.next_json_object()
                if spec is not None:
                    # JSON-сценарий сериализуется в content, если не задан явно.
                    if "content" not in spec:
                        spec = {
                            **spec,
                            "content": json.dumps(spec, ensure_ascii=False),
                        }
                    return self._response_from_spec(spec)
            if "память задачи диалога" in system_text.lower():
                return LlmResponse(
                    content=(
                        '{"goal": "уточнить детали проекта", '
                        '"constraints": ["только Python", "без внешних API"], '
                        '"terms": ["RAG — поиск по базе знаний"], '
                        '"clarifications": ["использовать локальную модель"]}'
                    ),
                    reasoning="[MOCK REASONING] JSON ответ для памяти задачи.",
                    prompt_tokens=100,
                    completion_tokens=20,
                )
            # Возвращаем JSON с тестовыми фактами для memory extraction в тестах
            return LlmResponse(
                content='{"facts": ["Пользователь предпочитает использовать Python для разработки", "Пользователь работает в Москве"]}',
                reasoning="[MOCK REASONING] JSON ответ для извлечения фактов.",
                prompt_tokens=100,
                completion_tokens=20,
            )

        # Сценарный ответ (если задан) имеет приоритет над echo-заглушкой.
        if self._scenario is not None:
            spec = self._scenario.next_response()
            if spec is not None:
                return self._response_from_spec(spec)

        # Получаем последнее сообщение пользователя для формирования ответа
        last_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        mock_content = f"[MOCK RESPONSE] Это тестовый ответ на ваш запрос: '{last_user_message[:50]}...'"
        mock_reasoning = (
            "[MOCK REASONING] Тестовые рассуждения для демонстрации функциональности."
        )

        return LlmResponse(
            content=mock_content,
            reasoning=mock_reasoning,
            prompt_tokens=100,
            completion_tokens=50,
        )
