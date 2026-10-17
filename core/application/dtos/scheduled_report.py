from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScheduledReport:
    """Результат одного запуска периодической агентной задачи.

    Слой представления (Celery) получает только этот DTO — ни репозиториев,
    ни LLM-провайдера, ни внутренностей агента он не видит.
    """

    chat_name: str
    agent_id: int | None
    task: str  # запрос, отправленный агенту
    answer: str  # итоговый ответ агента (сводка)
    prompt_tokens: int
    completion_tokens: int
