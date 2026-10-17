from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VectorSearchItem:
    """Результат векторного поиска."""

    chunk_id: int
    distance: float
