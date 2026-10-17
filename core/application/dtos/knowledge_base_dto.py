from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class KnowledgeBaseDTO:
    """Информация о базе знаний для отображения."""

    id: int
    name: str
    description: str | None
    embedding_model: str
    embedding_dimension: int
    created_at: datetime
    updated_at: datetime | None = None
    document_count: int | None = None
    chunk_count: int | None = None
