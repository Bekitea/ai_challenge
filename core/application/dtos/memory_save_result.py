from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MemorySaveResult:
    """Результат заполнения долговременной памяти одного чата.

    Attributes:
        chat_name: Имя чата, для которого сохранялась память.
        success: Успешно ли выполнено сохранение.
        duration_seconds: Сколько времени заняло заполнение памяти.
        error: Текст ошибки при неудаче (иначе None).
        timed_out: True, если ошибка вызвана таймаутом запроса к модели.
    """

    chat_name: str
    success: bool
    duration_seconds: float
    error: str | None = None
    timed_out: bool = False
