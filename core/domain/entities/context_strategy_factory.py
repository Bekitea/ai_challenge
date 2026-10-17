from __future__ import annotations

from typing import Any

from core.domain.entities.context_window_strategy import ContextWindowStrategy
from core.domain.entities.default_strategy import DefaultStrategy
from core.domain.entities.key_value_memory_strategy import KeyValueMemoryStrategy
from core.domain.entities.sliding_window_strategy import SlidingWindowStrategy
from core.domain.entities.summarization_strategy import SummarizationStrategy


def create_strategy_from_dict(data: dict[str, Any]) -> ContextWindowStrategy:
    """Фабричный метод для создания стратегии из словаря."""
    strategy_type = data.get("strategy_type", "DefaultStrategy")
    if strategy_type == "DefaultStrategy":
        return DefaultStrategy.from_dict(data)
    elif strategy_type == "SummarizationStrategy":
        return SummarizationStrategy.from_dict(data)
    elif strategy_type == "KeyValueMemoryStrategy":
        return KeyValueMemoryStrategy.from_dict(data)
    elif strategy_type == "SlidingWindowStrategy":
        return SlidingWindowStrategy.from_dict(data)
    else:
        raise ValueError(f"Неизвестный тип стратегии: {strategy_type}")
