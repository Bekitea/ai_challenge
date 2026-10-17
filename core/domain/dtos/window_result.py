from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WindowResult:
    """Результат применения стратегии к диалоговым сообщениям."""

    dialogue: list[Any]
    summary: str | None = None  # Итоговое саммари (старое или новое)
    summarization_tokens: tuple[int, int] | None = None  # Токены суммаризации
