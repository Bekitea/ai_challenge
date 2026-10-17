from __future__ import annotations

from collections.abc import Callable

from core.application.dtos.memory_save_result import MemorySaveResult
from core.application.protocols.llm_registry import LlmRegistry as LlmProviderRegistry
from core.application.use_cases._helpers.agent_access import _require_agent
from core.application.use_cases._helpers.memory_saver import _save_agent_memory
from core.domain.protocols.agent_repository import AgentRepository


class SaveAgentMemoryUseCase:
    """Use case для сохранения памяти агента при выходе из чата."""

    def __init__(
        self, repository: AgentRepository, registry: LlmProviderRegistry
    ):
        self.repository = repository
        self._registry = registry

    def execute(
        self,
        agent_id: int,
        on_warning: Callable[[str], None] | None = None,
    ) -> MemorySaveResult:
        """
        Сохраняет общесистемную память о пользователе и память профиля задачи.

        Args:
            agent_id: ID чата, для которого нужно сохранить память.
            on_warning: Необязательный колбэк для сообщений о сбое памяти задачи.

        Returns:
            Результат заполнения памяти чата (успех, длительность, ошибка).
        """
        agent = _require_agent(self.repository, agent_id)
        return _save_agent_memory(
            agent, self.repository, self._registry, on_warning=on_warning
        )
