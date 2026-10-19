from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskProfileInfo:
    """Информация о профиле задачи для отображения."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts_count: int
    preferences: str = ""
    invariants_count: int = 0
    mcp_servers: list[str] = field(default_factory=list)
