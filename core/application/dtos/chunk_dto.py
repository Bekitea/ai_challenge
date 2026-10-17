from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChunkDTO:
    """Информация о чанке документа (без эмбеддинга)."""

    id: int
    document_id: int
    chunk_index: int
    text: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    created_at: datetime
