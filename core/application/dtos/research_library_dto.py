from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime


@dataclass
class ResearchLibraryDTO:
    """Научная библиотека для presentation/MCP."""

    id: int
    name: str
    knowledge_base_id: int | None
    description: str | None = None
    goal: str | None = None
    field: str | None = None
    keywords: list[str] = dc_field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    language: str | None = None
    article_count: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
