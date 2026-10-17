from __future__ import annotations

from core.application.dtos.chat_dto import ChatDTO
from core.domain.entities.agent import Agent


def _agent_to_chat_dto(agent: Agent) -> ChatDTO:
    """Преобразует ``Agent`` в ``ChatDTO`` (без утечки бизнес-объекта)."""
    system_prompt = None
    for message in agent.get_history():
        if message.role == "system":
            system_prompt = message.content
            break
    return ChatDTO(
        agent_id=agent.agent_id,
        name=agent.name,
        strategy_type=agent.strategy.strategy_type,
        current_phase=agent.current_phase.name,
        system_prompt=system_prompt,
        task_profile_name=(
            agent.task_profile.name if agent.task_profile is not None else None
        ),
    )
