from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.domain.dtos.prompt import Prompt
from core.domain.dtos.window_result import WindowResult
from core.domain.entities.context_window_helpers import (
    align_group_boundary,
    group_tool_blocks,
)
from core.domain.entities.context_window_strategy import ContextWindowStrategy

if TYPE_CHECKING:
    from core.domain.protocols.llm_provider import LlmProvider


@dataclass
class BaseCompressionStrategy(ContextWindowStrategy):
    """Общая логика стратегий со суммаризацией.

    Параметры:
        non_compressible_count: Количество последних сообщений, которые не сжимаются.
        buffer_size: Размер буфера сообщений перед суммаризацией.

    Логика:
        - После накопления (non_compressible_count + buffer_size) сообщений
          первые (кратные buffer_size) сообщения суммаризируются.
        - Саммари хранится в поле стратегии и передаётся при следующей суммаризации.
        - Границы среза выравниваются по целым группам tool-вызовов.
        - История сохраняется полностью, суммаризация только для отправки в LLM.
    """

    non_compressible_count: int
    buffer_size: int
    _summary: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.non_compressible_count < 0:
            raise ValueError("non_compressible_count должен быть >= 0")
        if self.buffer_size <= 0:
            raise ValueError("buffer_size должен быть > 0")

    @property
    def summary(self) -> str | None:
        """Возвращает текущий саммари."""
        return self._summary

    @summary.setter
    def summary(self, value: str | None):
        """Устанавливает новый саммари."""
        self._summary = value

    def _summarization_system_prompt(self) -> str:
        """Возвращает системный промпт для выполнения суммаризации."""
        raise NotImplementedError

    def _summarization_kwargs(self) -> dict[str, Any]:
        """Дополнительные параметры запроса суммаризации."""
        return {}

    def apply(
        self,
        dialogue: list[Prompt],
        llm_provider: LlmProvider | None = None,
        model_id: str | None = None,
    ) -> WindowResult:
        """Сжимает старую часть диалога, сохраняя последние сообщения."""
        total = len(dialogue)
        threshold = self.non_compressible_count + self.buffer_size

        if total >= threshold and llm_provider is not None:
            count = total - self.non_compressible_count
            count = (count // self.buffer_size) * self.buffer_size
            count = align_group_boundary(group_tool_blocks(dialogue), count)

            if count > 0:
                new_summary, tech_tokens = self._perform_summarization(
                    dialogue[:count], llm_provider, model_id
                )
                self._summary = new_summary
                return WindowResult(
                    dialogue=dialogue[count:],
                    summary=new_summary,
                    summarization_tokens=tech_tokens,
                )

        return WindowResult(dialogue=list(dialogue), summary=self._summary)

    def _perform_summarization(
        self,
        messages_to_summarize: list[Prompt],
        llm_provider: LlmProvider,
        model_id: str | None = None,
    ) -> tuple[str, tuple[int, int]]:
        """Выполняет суммаризацию указанных сообщений через LLM.

        Returns:
            Кортеж (саммари, (prompt_tokens, completion_tokens)).
        """
        print(f"\n[INFO] Запущена суммаризация ({self.strategy_type})...")

        summarization_messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._summarization_system_prompt()}
        ]
        if self._summary:
            summarization_messages.append(
                {"role": "user", "content": f"Предыдущее саммари: {self._summary}"}
            )
        for msg in messages_to_summarize:
            summarization_messages.append(
                {"role": msg.role, "content": msg.content}
            )

        kwargs: dict[str, Any] = {
            "messages": summarization_messages,
            "temperature": 0.3,
            "max_tokens": 500,
            **self._summarization_kwargs(),
        }
        if model_id is not None:
            kwargs["model_id"] = model_id

        response = llm_provider.generate(**kwargs)

        prompt_tokens = response.prompt_tokens or 0
        completion_tokens = response.completion_tokens or 0
        return response.content, (prompt_tokens, completion_tokens)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "non_compressible_count": self.non_compressible_count,
            "buffer_size": self.buffer_size,
            "summary": self._summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseCompressionStrategy:
        instance = cls(
            non_compressible_count=data["non_compressible_count"],
            buffer_size=data["buffer_size"],
        )
        instance._summary = data.get("summary")
        return instance
