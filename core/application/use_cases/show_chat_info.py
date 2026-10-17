from __future__ import annotations

from core.application.dtos.chat_info import ChatInfo
from core.application.mappers.task_memory_mapper import _task_memory_to_dto
from core.application.use_cases._helpers.agent_access import _load_agent
from core.domain.protocols.agent_repository import AgentRepository


class ShowChatInfoUseCase:
    """Use case для показа информации о чате."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> ChatInfo | None:
        """
        Получает информацию о чате включая счетчики токенов (DTO).

        Args:
            agent_id: ID чата.

        Returns:
            ChatInfo или None, если чат не найден.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        agent.refresh_memory(self.repository)

        counters = agent.token_counters
        strategy = agent.strategy

        has_summary = False
        non_compressible_count = None
        buffer_size = None
        task_profile_name = None

        if hasattr(strategy, "summary") and strategy.summary:
            has_summary = True
        if hasattr(strategy, "non_compressible_count"):
            non_compressible_count = strategy.non_compressible_count
        if hasattr(strategy, "buffer_size"):
            buffer_size = strategy.buffer_size
        if agent.task_profile is not None:
            task_profile_name = agent.task_profile.name

        current_phase = agent.current_phase.value if agent.current_phase else None

        return ChatInfo(
            name=agent.name,
            agent_id=agent.agent_id,
            strategy_type=strategy.strategy_type,
            message_count=agent.message_count,
            total_prompt_tokens=counters.total_prompt_tokens,
            total_completion_tokens=counters.total_completion_tokens,
            has_summary=has_summary,
            non_compressible_count=non_compressible_count,
            buffer_size=buffer_size,
            task_profile_name=task_profile_name,
            current_phase=current_phase,
            task_memory=_task_memory_to_dto(agent.task_memory),
        )
