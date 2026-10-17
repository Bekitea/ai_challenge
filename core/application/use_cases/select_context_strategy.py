from __future__ import annotations

from core.application.dtos.strategy_selection import StrategySelection
from core.application.use_cases._helpers.strategy_builder import _build_strategy
from core.domain.entities.context_window_strategy import ContextWindowStrategy


class SelectContextStrategyUseCase:
    """Use case для выбора стратегии управления контекстным окном."""

    def execute(self, selection: StrategySelection) -> ContextWindowStrategy:
        """
        Создаёт стратегию на основе выбора пользователя.

        Args:
            selection: Выбранная стратегия с параметрами.

        Returns:
            ContextWindowStrategy: Экземпляр стратегии.
        """
        return _build_strategy(selection)
