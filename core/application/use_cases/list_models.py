from __future__ import annotations

from core.application.dtos.available_model import AvailableModel
from core.application.protocols.llm_registry import LlmRegistry as LlmProviderRegistry


class ListModelsUseCase:
    """Use case получения списка доступных моделей всех провайдеров.

    Опрашивает провайдеров динамически (Yandex Cloud и Ollama), поэтому
    хардкода моделей в приложении больше нет. Недоступный провайдер просто
    не попадает в результат.
    """

    def __init__(self, registry: LlmProviderRegistry):
        self._registry = registry

    def execute(self) -> list[AvailableModel]:
        """Возвращает список доступных моделей с указанием провайдера."""
        return [
            AvailableModel(
                provider=provider_name,
                model_id=info.model_id,
                display_name=info.display_name,
            )
            for provider_name, info in self._registry.list_models()
        ]
