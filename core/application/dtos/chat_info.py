from __future__ import annotations

from dataclasses import dataclass

from core.application.dtos.task_memory_dto import TaskMemoryDTO


@dataclass
class ChatInfo:
    """Информация о чате для отображения (DTO)."""

    name: str
    agent_id: int
    strategy_type: str
    message_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    has_summary: bool = False
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    task_profile_name: str | None = None
    current_phase: str | None = None
    task_memory: TaskMemoryDTO | None = None
