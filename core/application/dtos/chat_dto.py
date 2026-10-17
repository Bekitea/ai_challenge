from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChatDTO:
    """Идентификатор и базовые атрибуты чата (агенда)."""

    agent_id: int
    name: str
    strategy_type: str
    current_phase: str
    system_prompt: str | None = None
    task_profile_name: str | None = None
