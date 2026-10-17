from __future__ import annotations

from dataclasses import dataclass
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
