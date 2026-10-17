from __future__ import annotations

from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class RefreshAgentMemoryUseCase:
    """Use case для загрузки памяти агента при выборе чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int) -> None:
        """
        Загружает общесистемную память и память задачи для чата.

        Args:
            agent_id: ID чата, для которого нужно загрузить память.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is not None:
            agent.refresh_memory(self.repository)
