from __future__ import annotations

import time
from collections.abc import Callable

from core.application.dtos.memory_save_result import MemorySaveResult
from core.application.protocols.llm_registry import LlmRegistry as LlmProviderRegistry
from core.application.use_cases._helpers.llm_provider_resolver import (
    _resolve_llm_provider,
)
from core.domain.entities.agent import Agent
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.domain.protocols.agent_repository import AgentRepository


def _save_agent_memory(
    agent: Agent,
    repository: AgentRepository,
    registry: LlmProviderRegistry,
    on_warning: Callable[[str], None] | None = None,
) -> MemorySaveResult:
    """Заполняет глобальную и профильную память агента с замером времени."""
    start = time.perf_counter()
    try:
        llm_provider = _resolve_llm_provider(registry, agent)
        agent.save_memory(
            repository=repository,
            llm_provider=llm_provider,
            on_warning=on_warning,
        )
    except Exception as e:  # noqa: BLE001
        return MemorySaveResult(
            chat_name=agent.name,
            success=False,
            duration_seconds=time.perf_counter() - start,
            error=str(e),
            timed_out=isinstance(e, LlmTimeoutError),
        )
    return MemorySaveResult(
        chat_name=agent.name,
        success=True,
        duration_seconds=time.perf_counter() - start,
    )
