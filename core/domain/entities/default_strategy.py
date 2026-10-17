from __future__ import annotations

from typing import Any

from core.domain.dtos.prompt import Prompt
from core.domain.dtos.window_result import WindowResult
from core.domain.entities.context_window_strategy import ContextWindowStrategy


class DefaultStrategy(ContextWindowStrategy):
    """
    Стратегия по умолчанию: простая пересылка всех сообщений.
    При переполнении контекстного окна выбрасывается исключение.
    """

    def apply(
        self,
        dialogue: list[Prompt],
        llm_provider: Any = None,
        model_id: str | None = None,
    ) -> WindowResult:
        """Возвращает все диалоговые сообщения как есть."""
        return WindowResult(dialogue=list(dialogue))

    def to_dict(self) -> dict[str, Any]:
        return {"strategy_type": self.strategy_type}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DefaultStrategy:
        return cls()

    @property
    def strategy_type(self) -> str:
        return "DefaultStrategy"
