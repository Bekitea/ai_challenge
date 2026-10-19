from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchLibraryStatsDTO:
    """Сводная статистика научной библиотеки."""

    library_id: int
    library_name: str
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_year: dict[int, int] = field(default_factory=dict)
    with_summary: int = 0
    missing_summary: int = 0
    indexed_fulltext: int = 0
    abstract_only: int = 0
    errors: int = 0
