from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.tool_call_record import ToolCallRecord


@dataclass
class Prompt:
    """Сообщение в диалоге с агентом."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    timestamp: datetime | None = (
        None  # None для system, обязательно для user и assistant
    )
    reasoning: str | None = None  # Только для assistant
    settings: AgentSettings | None = (
        None  # Только для assistant (настройки на момент генерации)
    )
    prompt_tokens: int | None = None  # Только для assistant
    completion_tokens: int | None = None  # Только для assistant
    is_remembered: bool = False  # Пометка о прохождении через сохранение памяти
    tool_calls: list[ToolCallRecord] | None = None  # Только для assistant
    tool_call_id: str | None = None  # Только для role="tool"
    name: str | None = None  # Только для role="tool" (имя инструмента)
