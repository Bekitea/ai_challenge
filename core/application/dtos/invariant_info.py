from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InvariantInfo:
    """Информация об инварианте для отображения."""

    id: int
    text: str
    created_at: datetime
