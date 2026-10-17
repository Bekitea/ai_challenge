from __future__ import annotations

from dataclasses import dataclass

from core.domain.entities.base_compression_strategy import BaseCompressionStrategy


@dataclass
class SummarizationStrategy(BaseCompressionStrategy):
    """Стратегия с суммаризацией истории."""

    def _summarization_system_prompt(self) -> str:
        return (
            "Ты ассистент для суммаризации диалогов. "
            "Твоя задача — создать максимально краткое содержание предоставленной истории переписки. "
            "Включи только ключевые моменты: предпочтения пользователя, ограничения задачи и важные выводы. "
            "Не тяни бездумно все данные, а выделяй только существенную информацию. "
            "Если есть предыдущее саммари, объедини его с новыми сообщениями, сохраняя краткость."
        )

    @property
    def strategy_type(self) -> str:
        return "SummarizationStrategy"
