from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolCallRecord:
    """Запись о вызове инструмента, запрошенном моделью.

    Хранится в истории сообщений, чтобы при повторных запросах к LLM
    восстанавливать полный протокол tool calling.
    """

    id: str
    name: str  # префиксованное имя инструмента: "<server>__<tool>"
    arguments: str  # JSON-строка с аргументами
