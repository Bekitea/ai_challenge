from __future__ import annotations

import json

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.entities.agent_phase import AgentPhase


def _serialize_settings(settings: AgentSettings | None) -> str | None:
    """Сериализует AgentSettings в JSON строку."""
    if settings is None:
        return None
    return json.dumps(settings.to_dict())


def _deserialize_settings(json_str: str | None) -> AgentSettings | None:
    """Десериализует JSON строку в AgentSettings."""
    if json_str is None:
        return None
    data = json.loads(json_str)
    return AgentSettings(**data)


def _serialize_phase(phase: AgentPhase | None) -> str | None:
    """Сериализует AgentPhase в строку."""
    if phase is None:
        return None
    return phase.value


def _deserialize_phase(phase_str: str | None) -> AgentPhase | None:
    """Десериализует строку в AgentPhase."""
    if phase_str is None:
        return None
    return AgentPhase(phase_str)
