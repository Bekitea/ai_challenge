from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskMemory:
    """Память текущего диалога о задаче.

    Хранится per-chat (по ``conversation_id``) и подмешивается в системный
    блок на каждом сообщении, поэтому цель и зафиксированные договорённости
    не теряются на длинных диалогах.
    """

    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)
    updated_at: datetime | None = None

    def is_empty(self) -> bool:
        """Возвращает True, если память не содержит данных."""
        return not (
            self.goal or self.constraints or self.terms or self.clarifications
        )
