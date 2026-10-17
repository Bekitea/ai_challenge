from __future__ import annotations

from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ShowSummaryUseCase:
    """Use case для показа саммари диалога."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> str | None:
        """
        Получает саммари из стратегии чата.

        Args:
            agent_id: ID чата.

        Returns:
            Саммари или None, если оно отсутствует.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None

        strategy = agent.strategy
        if hasattr(strategy, "summary"):
            return strategy.summary
        return None
