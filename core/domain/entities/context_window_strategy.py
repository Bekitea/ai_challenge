from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from core.domain.dtos.prompt import Prompt
from core.domain.dtos.window_result import WindowResult

if TYPE_CHECKING:
    from core.domain.protocols.llm_provider import LlmProvider


class ContextWindowStrategy(ABC):
    """Абстрактный базовый класс для стратегий управления контекстным окном.

    Стратегия отвечает ТОЛЬКО за управление контекстным окном: какие
    диалоговые сообщения отправить в LLM и какое саммари к ним добавить.
    Подмешивание памяти, профиля и фазы — ответственность PromptBuilder.
    """

    @abstractmethod
    def apply(
        self,
        dialogue: list[Prompt],  # Список Prompt объектов (без system)
        llm_provider: LlmProvider | None = None,
        model_id: str | None = None,
    ) -> WindowResult:
        """Применяет стратегию к диалоговым сообщениям.

        Args:
            dialogue: Сообщения диалога в хронологическом порядке.
            llm_provider: Провайдер LLM для выполнения суммаризации.
            model_id: Идентификатор модели чата для служебных запросов.

        Returns:
            WindowResult: выбранные сообщения, саммари и токены суммаризации.
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Сериализует стратегию в словарь для хранения в БД."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextWindowStrategy:
        """Десериализует стратегию из словаря."""

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Возвращает тип стратегии (имя класса)."""
