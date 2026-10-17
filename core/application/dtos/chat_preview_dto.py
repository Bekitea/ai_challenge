from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatPreviewDTO:
    """Превью чата для списка чатов."""

    agent_id: int
    name: str
    last_message_timestamp: datetime | None
    message_count: int
    last_message_preview: str | None = None
