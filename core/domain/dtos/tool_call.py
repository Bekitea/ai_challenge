from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCall:
    """Вызов инструмента (tool call), запрошенный моделью."""

    id: str
    name: str
    arguments: Any  # dict или JSON-строка с аргументами
