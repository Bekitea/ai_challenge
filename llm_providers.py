from __future__ import annotations

import json
import logging
from typing import Any

import requests

from config import (
    AVAILABLE_EMBEDDING_MODELS,
    MODEL_LIST_TIMEOUT,
    OLLAMA_NATIVE_BASE_URL,
    OLLAMA_OPENAI_BASE_URL,
    YANDEX_BASE_URL,
)
from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.tool_call import ToolCall
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.domain.protocols.llm_provider import LlmProvider
from mock_llm import MockScenario, load_scenario_from_env

logger = logging.getLogger(__name__)


def _openai():
    """Ленивый импорт SDK ``openai``.

    SDK импортируется ~1.9 с и нужен только для реальных сетевых провайдеров.
    В TEST-режиме (mock-провайдеры) он вообще не должен загружаться — иначе
    каждый из сотен e2e-subprocess-запусков платит за него. Поэтому импорт
    выполняется только в момент фактического обращения к API.
    """
    import openai

    return openai


# Базовые имена embedding-моделей Ollama, которые не должны попадать в список
# чат-моделей (это модели для RAG, а не для генерации ответов).
_EMBEDDING_MODEL_NAMES = set(AVAILABLE_EMBEDDING_MODELS)


def _parse_openai_response(response: Any) -> LlmResponse:
    """Разбирает ответ OpenAI-совместимого API в ``LlmResponse``."""
    message = response.choices[0].message
    raw_content = message.content or ""
    reasoning_text = getattr(message, "reasoning_content", None) or getattr(
        message, "reasoning", None
    )

    tool_calls: list[ToolCall] | None = None
    raw_tool_calls = getattr(message, "tool_calls", None)
    if raw_tool_calls:
        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.function
            tool_calls.append(
                ToolCall(id=tc.id or "", name=fn.name, arguments=fn.arguments)
            )

    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

    return LlmResponse(
        content=raw_content,
        reasoning=reasoning_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        tool_calls=tool_calls,
    )


def _to_yandex_model_id(raw_id: str, folder_id: str) -> str:
    """Приводит id модели из ответа Yandex к нативному виду без ``gpt://folder/``."""
    if raw_id.startswith("gpt://"):
        rest = raw_id[len("gpt://") :]
        if "/" in rest:
            return rest.split("/", 1)[1]
        return rest
    return raw_id


class YandexCloudLlmProvider:
    """Провайдер для работы с Yandex Cloud LLM API."""

    provider_name = "yandex"

    def __init__(self, api_key: str, folder_id: str, base_url: str = YANDEX_BASE_URL):
        """Инициализирует клиент Yandex Cloud LLM.

        Args:
            api_key: API ключ для авторизации.
            folder_id: ID папки в Yandex Cloud.
            base_url: Базовый URL API (по умолчанию Yandex Cloud).
        """
        self.client = _openai().OpenAI(
            api_key=api_key, base_url=base_url, project=folder_id
        )
        self.folder_id = folder_id

    def list_models(self) -> list[LlmModelInfo]:
        """Возвращает список моделей Yandex Cloud через OpenAI-совместимый /models.

        При недоступности API (нет сети, нет прав) возвращает пустой список.
        """
        try:
            response = self.client.models.list(timeout=MODEL_LIST_TIMEOUT)
        except Exception as exc:  # noqa: BLE001 — любая ошибка => провайдер недоступен
            logger.warning("Не удалось получить список моделей Yandex: %s", exc)
            return []

        models: list[LlmModelInfo] = []
        for item in getattr(response, "data", []) or []:
            raw_id = getattr(item, "id", None)
            if not raw_id:
                continue
            native_id = _to_yandex_model_id(raw_id, self.folder_id)
            models.append(LlmModelInfo(model_id=native_id, display_name=native_id))
        return models

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
        """Генерирует ответ от Yandex Cloud LLM.

        Args:
            messages: Список сообщений в формате [{"role": "...", "content": "..."}].
            temperature: Температура генерации (0.0 - 2.0).
            max_tokens: Максимальное количество токенов в ответе.
            timeout: Таймаут запроса в секундах.
            top_p: Параметр выборки ядра (nucleus sampling).
            top_k: Параметр топ-K выборки.
            response_format: Формат ответа (например, JSON schema).
            reasoning_effort: Уровень усилий рассуждений ("low", "medium", "high", "none").
            model_id: Идентификатор модели (обязателен: дефолтной модели нет).
            tools: Список инструментов (OpenAI-compatible) для function calling (MCP).
            max_retries: Число повторов запроса в SDK (None — дефолт клиента).

        Returns:
            LlmResponse: Объект с содержимым ответа и текстом рассуждений.

        Raises:
            ValueError: Если ``model_id`` не указан.
            LlmTimeoutError: При таймауте запроса.
            openai.APIError: При ошибке запроса к API.
        """
        if model_id is None:
            raise ValueError("YandexCloudLlmProvider: model_id обязателен")

        kwargs: dict[str, Any] = {
            "model": f"gpt://{self.folder_id}/{model_id}",
            "messages": messages,
            "timeout": timeout,
        }

        # Добавляем только переданные параметры
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if top_k is not None:
            kwargs["top_k"] = top_k
        if response_format is not None:
            kwargs["response_format"] = response_format
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs["tools"] = tools

        client = self.client
        if max_retries is not None:
            client = client.with_options(max_retries=max_retries)

        try:
            response = client.chat.completions.create(**kwargs)
        except _openai().APITimeoutError as e:
            raise LlmTimeoutError(str(e)) from e
        return _parse_openai_response(response)


class OllamaLlmProvider:
    """Провайдер для локальных моделей Ollama (OpenAI-совместимый ``/v1``).

    Генерация идёт через ``POST {OLLAMA_OPENAI_BASE_URL}/chat/completions`` (тот
    же ``openai`` SDK, что и у Yandex), а список моделей — через
    ``GET {OLLAMA_NATIVE_BASE_URL}/api/tags`` (нативный и стабильный эндпоинт
    Ollama). При включённом LLM Gateway оба URL указывают на gateway, а не на
    Ollama напрямую.
    """

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = OLLAMA_OPENAI_BASE_URL,
        native_base_url: str = OLLAMA_NATIVE_BASE_URL,
    ):
        """Инициализирует клиент Ollama.

        Args:
            base_url: OpenAI-совместимый базовый URL (``.../v1``).
            native_base_url: Нативный базовый URL Ollama (без ``/v1``).
        """
        self.client = _openai().OpenAI(api_key="ollama", base_url=base_url)
        self.native_base_url = native_base_url.rstrip("/")

    def list_models(self) -> list[LlmModelInfo]:
        """Возвращает список локальных чат-моделей Ollama.

        Embedding-модели (например ``bge-m3``) отфильтровываются: они
        предназначены для RAG и непригодны для генерации ответов.
        """
        try:
            response = requests.get(
                f"{self.native_base_url}/api/tags", timeout=MODEL_LIST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001 — любая ошибка => Ollama недоступна
            logger.warning("Не удалось получить список моделей Ollama: %s", exc)
            return []

        models: list[LlmModelInfo] = []
        for item in data.get("models", []) or []:
            name = item.get("name") or item.get("model")
            if not name:
                continue
            base_name = name.split(":")[0]
            if base_name in _EMBEDDING_MODEL_NAMES or "embed" in base_name.lower():
                continue
            models.append(LlmModelInfo(model_id=name, display_name=name))
        return models

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
        """Генерирует ответ от локальной модели Ollama.

        Поддерживаются ``temperature``, ``max_tokens``, ``top_p``, ``tools``,
        ``response_format`` и ``reasoning_effort`` (управление рассуждениями
        thinking-моделей; ``"none"`` отключает их). Параметр ``top_k``
        OpenAI-совместимым API Ollama не поддерживается и игнорируется.

        Raises:
            ValueError: Если ``model_id`` не указан.
            LlmTimeoutError: При таймауте запроса.
        """
        if model_id is None:
            raise ValueError("OllamaLlmProvider: model_id обязателен")

        kwargs: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "timeout": timeout,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            kwargs["top_p"] = top_p
        if response_format is not None:
            kwargs["response_format"] = response_format
        if reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort
        if tools:
            kwargs["tools"] = tools

        client = self.client
        if max_retries is not None:
            client = client.with_options(max_retries=max_retries)

        try:
            response = client.chat.completions.create(**kwargs)
        except _openai().APITimeoutError as e:
            raise LlmTimeoutError(str(e)) from e
        return _parse_openai_response(response)


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
        top_k: int | None = None,
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


class LlmProviderRegistry:
    """Набор именованных LLM-провайдеров, доступных приложению.

    Позволяет чату выбрать провайдера по имени из ``AgentSettings.provider``
    и агрегировать список моделей всех провайдеров для UI.
    """

    def __init__(self, providers: dict[str, LlmProvider]):
        """Args: providers: словарь {provider_name: provider}."""
        self._providers = dict(providers)

    def get(self, name: str) -> LlmProvider | None:
        """Возвращает провайдера по имени или ``None``."""
        return self._providers.get(name)

    def all(self) -> dict[str, LlmProvider]:
        """Возвращает копию словаря всех провайдеров."""
        return dict(self._providers)

    def list_models(self) -> list[tuple[str, LlmModelInfo]]:
        """Агрегирует модели всех провайдеров.

        Возвращает список пар ``(provider_name, model_info)``. Провайдер,
        бросивший исключение или недоступный, молча пропускается.
        """
        result: list[tuple[str, LlmModelInfo]] = []
        for name, provider in self._providers.items():
            try:
                provider_models = provider.list_models()
            except Exception as exc:  # noqa: BLE001 — провайдер недоступен
                logger.warning(
                    "Провайдер '%s' недоступен при опросе моделей: %s", name, exc
                )
                continue
            result.extend((name, info) for info in provider_models)
        return result
