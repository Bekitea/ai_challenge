from __future__ import annotations

from core.application.dtos.task_memory_dto import TaskMemoryDTO
from core.domain.dtos.task_memory import TaskMemory


def _task_memory_to_dto(memory: TaskMemory) -> TaskMemoryDTO:
    """Преобразует бизнес-объект памяти задачи в DTO."""
    return TaskMemoryDTO(
        goal=memory.goal,
        constraints=list(memory.constraints),
        terms=list(memory.terms),
        clarifications=list(memory.clarifications),
    )
