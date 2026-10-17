from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ApiKeyDTO:
    """Метаданные API-ключа без секрета."""

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
