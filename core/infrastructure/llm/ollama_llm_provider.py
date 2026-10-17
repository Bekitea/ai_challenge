from __future__ import annotations

import logging
from typing import Any

import requests

from config import (
    MODEL_LIST_TIMEOUT,
    OLLAMA_NATIVE_BASE_URL,
    OLLAMA_OPENAI_BASE_URL,
)
from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.dtos.llm_response import LlmResponse
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.infrastructure.llm.openai_response_parser import (
    _EMBEDDING_MODEL_NAMES,
    _openai,
    _parse_openai_response,
)

logger = logging.getLogger(__name__)


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
