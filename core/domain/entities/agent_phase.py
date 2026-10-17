from __future__ import annotations

from enum import Enum


class AgentPhase(Enum):
    """Фазы работы агента."""

    PLAN = "plan"
    EXECUTE = "execute"
    VALIDATE = "validate"
    REPORT = "report"

    def get_description(self) -> str:
        """Возвращает описание фазы."""
        descriptions = {
            AgentPhase.PLAN: (
                "Фаза: Планирование\n"
                "Действия: Обсуди со мной задачу, задавай вопросы, пока тебе не станут кристально ясны все нюансы. "
                "Менять на этой фазе содержимое проекта строго запрещено. Переход в другую фазу только по согласию пользователя. "
                "Если вопросов больше нет, то составь детальный план и явно запроси переход у пользователя."
            ),
            AgentPhase.EXECUTE: (
                "Фаза: Исполнение\n"
                "Действия: Нужно выполнять план. Выполняй, пока он не будет завершен полностью. "
                "Если всё сделано, то явно запроси переход у пользователя."
            ),
            AgentPhase.VALIDATE: (
                "Фаза: Тестирование\n"
                "Действия: Нужно проверить результат на соответствие запросу пользователя. "
                "Исправь проблемы. Если всё сделано, то явно запроси переход у пользователя."
            ),
            AgentPhase.REPORT: (
                "Фаза: Отчет\nДействия: Нужно предоставить отчет по итогам работы."
            ),
        }
        return descriptions.get(self, "")

    @staticmethod
    def serialize(phase: AgentPhase) -> str:
        """Сериализует фазу в строку для хранения в БД."""
        return phase.value

    @staticmethod
    def deserialize(value: str | None) -> AgentPhase:
        """Десериализует фазу из строки БД."""
        if value is None:
            return AgentPhase.PLAN
        for phase in AgentPhase:
            if phase.value == value:
                return phase
        return AgentPhase.PLAN
