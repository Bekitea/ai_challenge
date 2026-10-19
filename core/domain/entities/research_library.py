from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime


@dataclass
class ResearchLibrary:
    """Научная библиотека: одна диссертация/область со своей БЗ и профилем."""

    id: int | None
    name: str
    knowledge_base_id: int | None = None
    description: str | None = None
    goal: str | None = None
    field: str | None = None
    keywords: list[str] = dc_field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    language: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
