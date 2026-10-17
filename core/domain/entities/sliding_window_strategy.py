from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.domain.dtos.prompt import Prompt
from core.domain.dtos.window_result import WindowResult
from core.domain.entities.context_window_helpers import align_window_start
from core.domain.entities.context_window_strategy import ContextWindowStrategy


@dataclass
class SlidingWindowStrategy(ContextWindowStrategy):
    """
    Стратегия скользящего окна (Sliding Window).

    Параметры:
        window_size: Количество последних сообщений, которые передаются в LLM.

    Логика:
        - Для LLM отправляются только последние N сообщений.
        - Окно выравнивается по целым группам tool-вызовов.
        - История сохраняется полностью, но для LLM отправляется только окно.
    """

    window_size: int

    def __post_init__(self):
        if self.window_size <= 0:
            raise ValueError("window_size должен быть > 0")

    def apply(
        self,
        dialogue: list[Prompt],
        llm_provider: Any = None,
        model_id: str | None = None,
    ) -> WindowResult:
        """Возвращает последние window_size сообщений (с выравниванием)."""
        start = max(0, len(dialogue) - self.window_size)
        aligned_start = align_window_start(dialogue, start)
        return WindowResult(dialogue=dialogue[aligned_start:])

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "window_size": self.window_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlidingWindowStrategy:
        return cls(window_size=data["window_size"])

    @property
    def strategy_type(self) -> str:
        return "SlidingWindowStrategy"
