from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PreparedMessages:
    """Результат подготовки сообщений для отправки в LLM."""

    messages: list[dict[str, Any]]
    summary: str | None = None
    summarization_tokens: tuple[int, int] | None = None
