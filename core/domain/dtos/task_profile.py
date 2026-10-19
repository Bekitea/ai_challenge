from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskProfile:
    """Профиль задачи с фактами памяти и MCP-инструментами."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts: list[str] = field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
