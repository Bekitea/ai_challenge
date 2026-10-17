from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskProfileDetailDTO:
    """Профиль задачи с полной памятью (факты + инварианты)."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts: list[str] = field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = field(default_factory=list)
