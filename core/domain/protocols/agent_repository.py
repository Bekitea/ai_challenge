from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.domain.dtos.agent_preview import AgentPreview
from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.task_memory import TaskMemory

if TYPE_CHECKING:
    from core.domain.entities.agent import Agent
    from core.domain.entities.agent_phase import AgentPhase
    from core.domain.entities.context_window_strategy import ContextWindowStrategy


class AgentRepository(Protocol):
    """Единый порт репозитория агента.

    Отвечает и за CRUD чатов, и за персистентность памяти/истории, к которой
    агент обращается в методах диалога. Реализация — ``PersistentAgentRepository``.
    """

    # --- CRUD чатов -----------------------------------------------------

    def create_agent(
        self,
        name: str,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        strategy: ContextWindowStrategy | None = None,
        task_profile_id: str | None = None,
        initial_phase: AgentPhase | None = None,
    ) -> Agent: ...

    def get_agent(self, agent_id: int) -> Agent | None: ...

    def get_all_previews(self) -> list[AgentPreview]: ...

    def update_agent(self, agent: Agent) -> None: ...

    def delete_agent(self, agent_id: int) -> bool: ...

    def get_agents_with_unsaved_memory(self) -> list[Agent]: ...

    # --- Память и история ----------------------------------------------

    def get_global_memory(self) -> GlobalMemory: ...

    def save_global_memory(self, memory: GlobalMemory) -> None: ...

    def get_task_memory(self, conversation_id: str) -> TaskMemory | None: ...

    def save_task_memory(self, conversation_id: str, memory: TaskMemory) -> None: ...

    def save_task_profile_facts(
        self, profile_id: str, facts: list[str]
    ) -> None: ...

    def delete_task_memory(self, conversation_id: str) -> None: ...
