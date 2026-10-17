from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DocumentDTO:
    """Информация о документе базы знаний."""

    id: int
    knowledge_base_id: int
    name: str
    source_type: str
    source_path: str | None
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None
