from __future__ import annotations

from typing import Protocol

from core.domain.dtos.task_memory import TaskMemory


class TaskMemoryRepository(Protocol):
    """Порт хранилища памяти задачи диалога (per-chat)."""

    def get_memory(self, conversation_id: str) -> TaskMemory | None: ...

    def save_memory(self, conversation_id: str, memory: TaskMemory) -> None: ...

    def delete_memory(self, conversation_id: str) -> None: ...
