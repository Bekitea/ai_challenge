from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from config import YANDEX_BASE_URL


@dataclass
class ToolCall:
    """Вызов инструмента (tool call), запрошенный моделью."""

    id: str
    name: str
    arguments: Any  # dict или JSON-строка с аргументами


@dataclass
class LlmResponse:
    """Результат ответа от LLM."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tool_calls: list[ToolCall] | None = None  # Вызовы инструментов (MCP)


class LlmProvider(ABC):
    """Протокол для провайдеров LLM.

    Позволяет добавлять новых провайдеров (OpenAI, Anthropic, etc.)
    без изменения основного кода приложения.
    """

    @abstractmethod
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
    ) -> LlmResponse:
        """Генерирует ответ от LLM.

        Args:
            messages: Список сообщений в формате [{"role": "...", "content": "..."}].
            temperature: Температура генерации (0.0 - 2.0).
            max_tokens: Максимальное количество токенов в ответе.
            timeout: Таймаут запроса в секундах.
            top_p: Параметр выборки ядра (nucleus sampling).
            top_k: Параметр топ-K выборки.
            response_format: Формат ответа (например, JSON schema).
            reasoning_effort: Уровень усилий рассуждений ("low", "medium", "high", "none").
            model_id: Идентификатор модели (если не указан, используется модель по умолчанию).
            tools: Список инструментов (OpenAI-compatible) для function calling (MCP).

        Returns:
            LlmResponse: Объект с содержимым ответа и текстом рассуждений.

        Raises:
            Exception: При ошибке запроса к API.
        """


class YandexCloudLlmProvider(LlmProvider):
    """Провайдер для работы с Yandex Cloud LLM API."""

    def __init__(self, api_key: str, folder_id: str, base_url: str = YANDEX_BASE_URL):
        """Инициализирует клиент Yandex Cloud LLM.

        Args:
            api_key: API ключ для авторизации.
            folder_id: ID папки в Yandex Cloud.
            base_url: Базовый URL API (по умолчанию Yandex Cloud).
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url, project=folder_id)
        self.folder_id = folder_id

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
            model_id: Идентификатор модели (если не указан, используется модель по умолчанию).
            tools: Список инструментов (OpenAI-compatible) для function calling (MCP).

        Returns:
            LlmResponse: Объект с содержимым ответа и текстом рассуждений.

        Raises:
            openai.APIError: При ошибке запроса к API.
        """
        if model_id is None:
            from config import YANDEX_DEFAULT_MODEL

            model_id = YANDEX_DEFAULT_MODEL

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

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        raw_content = message.content or ""
        reasoning_text = getattr(message, "reasoning_content", None) or getattr(
            message, "reasoning", None
        )

        # Разбираем вызовы инструментов (MCP tool calls)
        tool_calls: list[ToolCall] | None = None
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.function
                tool_calls.append(
                    ToolCall(
                        id=tc.id or "",
                        name=fn.name,
                        arguments=fn.arguments,
                    )
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


class MockLlmProvider(LlmProvider):
    """Mock-провайдер для тестирования без реального API.

    Возвращает заглушки вместо реальных запросов к LLM.
    """

    def __init__(self):
        """Инициализирует mock-провайдер."""

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

        Returns:
            LlmResponse: Mock-объект с содержимым ответа.
        """
        # Проверяем, запрошен ли JSON формат (для извлечения фактов памяти)
        if response_format and response_format.get("type") == "json_object":
            # Возвращаем JSON с тестовыми фактами для memory extraction в тестах
            return LlmResponse(
                content='{"facts": ["Пользователь предпочитает использовать Python для разработки", "Пользователь работает в Москве"]}',
                reasoning="[MOCK REASONING] JSON ответ для извлечения фактов.",
                prompt_tokens=100,
                completion_tokens=20,
            )

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
