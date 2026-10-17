from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskMemoryDTO:
    """DTO памяти задачи текущего диалога."""

    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Возвращает True, если память не содержит данных."""
        return not (
            self.goal or self.constraints or self.terms or self.clarifications
        )
