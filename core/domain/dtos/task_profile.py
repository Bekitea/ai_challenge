from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskProfile:
    """Профиль задачи с памятью о фактах задачи."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts: list[str] = field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = field(default_factory=list)
