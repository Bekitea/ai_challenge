from __future__ import annotations

from core.domain.entities.agent import Agent
from core.domain.protocols.agent_repository import AgentRepository


def _load_agent(repository: AgentRepository, agent_id: int | None) -> Agent | None:
    """Загружает агента по ``agent_id`` (None-safe)."""
    if agent_id is None:
        return None
    return repository.get_agent(agent_id)


def _require_agent(repository: AgentRepository, agent_id: int) -> Agent:
    """Загружает агента или бросает ValueError, если он не найден."""
    agent = repository.get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Чат #{agent_id} не найден")
    return agent
