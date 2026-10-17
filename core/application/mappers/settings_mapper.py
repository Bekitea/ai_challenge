from __future__ import annotations

from core.application.dtos.settings_dto import SettingsDTO
from core.domain.dtos.agent_settings import AgentSettings


def _settings_to_agent_settings(dto: SettingsDTO) -> AgentSettings:
    """Преобразует DTO настроек в бизнес-объект ``AgentSettings``."""
    return AgentSettings(
        model_id=dto.model_id,
        provider=dto.provider,
        top_k=dto.top_k,
        top_p=dto.top_p,
        temperature=dto.temperature,
        max_tokens=dto.max_tokens,
        reasoning_effort=dto.reasoning_effort,
        context_window_size=dto.context_window_size,
        reranker_enabled=dto.reranker_enabled,
    )


def _agent_settings_to_dto(settings: AgentSettings) -> SettingsDTO:
    """Преобразует ``AgentSettings`` в DTO настроек."""
    return SettingsDTO(
        model_id=settings.model_id,
        provider=settings.provider,
        top_k=settings.top_k,
        top_p=settings.top_p,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        reasoning_effort=settings.reasoning_effort,
        context_window_size=settings.context_window_size,
        reranker_enabled=settings.reranker_enabled,
    )
