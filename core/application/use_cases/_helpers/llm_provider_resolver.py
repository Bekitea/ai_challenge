from __future__ import annotations

from config import (
    DEFAULT_PROVIDER,
)
from core.application.protocols.llm_registry import LlmRegistry as LlmProviderRegistry
from core.domain.entities.agent import Agent
from core.domain.protocols.llm_provider import LlmProvider


def _resolve_llm_provider(
    registry: LlmProviderRegistry, agent: Agent
) -> LlmProvider:
    """Возвращает провайдера, выбранного в настройках чата.

    Если провайдер не задан (старые чаты), используется ``DEFAULT_PROVIDER``.
    """
    provider_name = agent.get_settings().provider or DEFAULT_PROVIDER
    provider = registry.get(provider_name)
    if provider is None:
        available = ", ".join(registry.all()) or "нет"
        raise ValueError(
            f"Провайдер '{provider_name}' недоступен. "
            f"Доступные провайдеры: {available}."
        )
    return provider
