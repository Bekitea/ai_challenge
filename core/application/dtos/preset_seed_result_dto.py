from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PresetSeedResultDTO:
    """Результат создания предустановленных профилей задачи."""

    created: int = 0
    skipped: int = 0
    names: list[str] = field(default_factory=list)
