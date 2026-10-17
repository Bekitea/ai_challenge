from __future__ import annotations

from core.application.dtos.phase_change_result_dto import PhaseChangeResultDTO
from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class ChangePhaseUseCase:
    """Use case перехода агента между фазами (PLAN/EXECUTE/VALIDATE/REPORT)."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, command: str) -> PhaseChangeResultDTO:
        """Обрабатывает команду перехода по фазам (``/plan``, ``/execute``, …)."""
        agent = _require_agent(self.repository, agent_id)
        success, message = agent.handle_phase_command(command, self.repository)
        return PhaseChangeResultDTO(
            success=success,
            message=message,
            current_phase=agent.current_phase.name,
        )
