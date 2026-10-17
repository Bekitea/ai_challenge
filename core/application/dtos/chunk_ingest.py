from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class ChunkIngest:
    """Чанк с эмбеддингом для сохранения при индексации."""

    chunk_index: int
    text: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    embedding: Sequence[float]
