from __future__ import annotations

from core.application.dtos.strategy_selection import StrategySelection
from core.domain.entities.context_window_strategy import ContextWindowStrategy
from core.domain.entities.default_strategy import DefaultStrategy
from core.domain.entities.key_value_memory_strategy import KeyValueMemoryStrategy
from core.domain.entities.sliding_window_strategy import SlidingWindowStrategy
from core.domain.entities.summarization_strategy import SummarizationStrategy


def _build_strategy(selection: StrategySelection) -> ContextWindowStrategy:
    """Создаёт стратегию управления контекстом из DTO-описания выбора."""
    if selection.strategy_type == "SummarizationStrategy":
        return SummarizationStrategy(
            non_compressible_count=selection.non_compressible_count or 2,
            buffer_size=selection.buffer_size or 3,
        )
    if selection.strategy_type == "KeyValueMemoryStrategy":
        return KeyValueMemoryStrategy(
            non_compressible_count=selection.non_compressible_count or 2,
            buffer_size=selection.buffer_size or 3,
        )
    if selection.strategy_type == "SlidingWindowStrategy":
        return SlidingWindowStrategy(window_size=selection.window_size or 10)
    return DefaultStrategy()
