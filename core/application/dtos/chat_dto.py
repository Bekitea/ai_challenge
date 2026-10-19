from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatDTO:
    """Идентификатор и детали текущего чата (агента)."""

    agent_id: int
    name: str
    strategy_type: str
    current_phase: str
    system_prompt: str | None = None
    task_profile_name: str | None = None
    mcp_messages: list[str] = field(default_factory=list)
