from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class HistoryMessageDTO:
    """Одно сообщение истории диалога (DTO)."""

    role: str
    content: str
    reasoning: str | None = None
    has_tool_calls: bool = False
    timestamp: datetime | None = None
