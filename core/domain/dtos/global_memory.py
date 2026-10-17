from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GlobalMemory:
    """Общесистемная память о пользователе."""

    facts: list[str] = field(default_factory=list)
