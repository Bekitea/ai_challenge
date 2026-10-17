from __future__ import annotations

import logging

from core.domain.dtos.llm_model_info import LlmModelInfo
from core.domain.protocols.llm_provider import LlmProvider

logger = logging.getLogger(__name__)


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
