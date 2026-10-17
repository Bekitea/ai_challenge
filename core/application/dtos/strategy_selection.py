from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategySelection:
    """Выбранная стратегия с параметрами."""

    strategy_type: str
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    window_size: int | None = None
