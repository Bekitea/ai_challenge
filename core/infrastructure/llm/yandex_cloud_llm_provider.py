from __future__ import annotations

import logging
from typing import Any

from config import MODEL_LIST_TIMEOUT, YANDEX_BASE_URL
from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.dtos.llm_response import LlmResponse
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.infrastructure.llm.openai_response_parser import (
    _openai,
    _parse_openai_response,
    _to_yandex_model_id,
)

logger = logging.getLogger(__name__)


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
