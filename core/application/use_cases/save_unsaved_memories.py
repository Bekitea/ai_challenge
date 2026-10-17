from __future__ import annotations

from collections.abc import Callable

from core.application.dtos.memory_save_result import MemorySaveResult
from core.application.protocols.llm_registry import LlmRegistry as LlmProviderRegistry
from core.application.use_cases._helpers.memory_saver import _save_agent_memory
from core.domain.protocols.agent_repository import AgentRepository


class SaveUnsavedMemoriesUseCase:
    """Use case для сохранения всех несохранённых памятей при старте приложения."""

    def __init__(
        self, repository: AgentRepository, registry: LlmProviderRegistry
    ):
        self.repository = repository
        self._registry = registry

    def execute(
        self,
        on_agent_start: Callable[[str], None] | None = None,
        on_result: Callable[[MemorySaveResult], None] | None = None,
        on_warning: Callable[[str], None] | None = None,
    ) -> list[MemorySaveResult]:
        """
        Находит все агенты с несохранёнными промптами и сохраняет их память.

        Агент считается имеющим несохранённые промпты, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False

        Если сохранение одного чата падает по таймауту модели, обработка серии
        прерывается (circuit breaker), оставшиеся чаты пропускаются с
        предупреждением через ``on_warning``.

        Args:
            on_agent_start: Необязательный колбэк(chat_name), вызывается перед
                сохранением памяти каждого чата.
            on_result: Необязательный колбэк(MemorySaveResult), вызывается
                сразу после сохранения памяти каждого чата.
            on_warning: Необязательный колбэк(сообщение) для сбоев памяти задачи.

        Returns:
            Список результатов по каждому чату (успех, длительность, ошибка).
        """
        agents = self.repository.get_agents_with_unsaved_memory()

        results: list[MemorySaveResult] = []
        for index, agent in enumerate(agents):
            if on_agent_start is not None:
                on_agent_start(agent.name)
            result = _save_agent_memory(
                agent, self.repository, self._registry, on_warning=on_warning
            )
            results.append(result)
            if on_result is not None:
                on_result(result)
            if result.timed_out:
                skipped = len(agents) - index - 1
                if on_warning is not None and skipped:
                    on_warning(
                        "Сохранение памяти прервано из-за таймаута модели; "
                        f"пропущено чатов: {skipped}."
                    )
                break
        return results
