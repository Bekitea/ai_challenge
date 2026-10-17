from __future__ import annotations


class ViewGlobalMemoryUseCase:
    """Use case для просмотра глобальной памяти агента."""

    def __init__(self, memory_repository):
        self.memory_repository = memory_repository

    def execute(self) -> list[str]:
        """
        Получает список фактов из глобальной памяти.

        Returns:
            Список фактов.
        """
        memory = self.memory_repository.get_memory()
        return memory.facts
