from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class VectorInsertItem:
    """Вектор чанка для вставки в векторную таблицу."""

    chunk_id: int
    embedding: Sequence[float]
