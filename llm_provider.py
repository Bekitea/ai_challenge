from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import openai
from openai import OpenAI

from config import BASE_URL


@dataclass
class LlmResponse:
    """Результат ответа от LLM."""
    content: str
    reasoning: Optional[str] = None


class LlmProvider(ABC):
    """Протокол для провайдеров LLM.
    
    Позволяет добавлять новых провайдеров (OpenAI, Anthropic, etc.)
    без изменения основного кода приложения.
    """

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 20,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        response_format: Optional[dict] = None,
        reasoning_effort: Optional[str] = None,
        model_id: Optional[str] = None,
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

        Returns:
            LlmResponse: Объект с содержимым ответа и текстом рассуждений.

        Raises:
            Exception: При ошибке запроса к API.
        """
        pass


class YandexCloudLlmProvider(LlmProvider):
    """Провайдер для работы с Yandex Cloud LLM API."""

    def __init__(self, api_key: str, folder_id: str, base_url: str = BASE_URL):
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
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 20,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        response_format: Optional[dict] = None,
        reasoning_effort: Optional[str] = None,
        model_id: Optional[str] = None,
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

        Returns:
            LlmResponse: Объект с содержимым ответа и текстом рассуждений.

        Raises:
            openai.APIError: При ошибке запроса к API.
        """
        if model_id is None:
            from config import YANDEX_CLOUD_MODEL
            model_id = YANDEX_CLOUD_MODEL

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

        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        raw_content = message.content or ""
        reasoning_text = getattr(message, "reasoning_content", None) or getattr(
            message, "reasoning", None
        )

        return LlmResponse(content=raw_content, reasoning=reasoning_text)
