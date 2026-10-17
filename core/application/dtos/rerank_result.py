from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RerankResult:
    """Результат реранкинга одного документа."""

    index: int
    score: float
    text: str | None = None
