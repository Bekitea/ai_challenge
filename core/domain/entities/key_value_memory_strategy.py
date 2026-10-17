from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.domain.entities.base_compression_strategy import BaseCompressionStrategy

# JSON схема для KeyValueMemoryStrategy
KEY_VALUE_MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "цель": {"type": "string", "description": "Основная цель диалога или задачи"},
        "ограничения": {
            "type": "string",
            "description": "Ограничения и требования к решению",
        },
        "предпочтения": {"type": "string", "description": "Предпочтения пользователя"},
        "решения": {
            "type": "string",
            "description": "Принятые решения и их обоснование",
        },
        "договоренности": {
            "type": "string",
            "description": "Достигнутые договоренности",
        },
    },
    "required": ["цель", "ограничения", "предпочтения", "решения", "договоренности"],
}


@dataclass
class KeyValueMemoryStrategy(BaseCompressionStrategy):
    """Стратегия с суммаризацией истории в формате JSON (Key-Value Memory).

    Саммари хранится в виде JSON со строгой схемой:
    ключи: цель, ограничения, предпочтения, решения, договоренности.
    """

    def _summarization_system_prompt(self) -> str:
        return (
            "Ты ассистент для суммаризации диалогов. "
            "Твоя задача — создать максимально краткое содержание предоставленной истории переписки "
            "в формате JSON со строгой схемой.\n\n"
            "СХЕМА JSON (обязательно следуй ей):\n"
            "{\n"
            '  "цель": "Основная цель диалога или задачи",\n'
            '  "ограничения": "Ограничения и требования к решению",\n'
            '  "предпочтения": "Предпочтения пользователя",\n'
            '  "решения": "Принятые решения и их обоснование",\n'
            '  "договоренности": "Достигнутые договоренности"\n'
            "}\n\n"
            "Включи только ключевые моменты по каждому полю. "
            "Если информации по какому-то полю нет, укажи пустую строку. "
            "Не тяни бездумно все данные, а выделяй только существенную информацию. "
            "Если есть предыдущее саммари, объедини его с новыми сообщениями, сохраняя краткость. "
            "Ответ должен быть ТОЛЬКО валидным JSON без дополнительного текста."
        )

    def _summarization_kwargs(self) -> dict[str, Any]:
        return {"response_format": {"type": "json_object"}}

    @property
    def strategy_type(self) -> str:
        return "KeyValueMemoryStrategy"
