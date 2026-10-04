from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from llm_providers import LlmProvider

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
class WindowResult:
    """Результат применения стратегии к диалоговым сообщениям."""

    dialogue: list[Any]
    summary: str | None = None  # Итоговое саммари (старое или новое)
    summarization_tokens: tuple[int, int] | None = None  # Токены суммаризации


def prompt_to_llm_dict(msg: Any) -> dict[str, Any]:
    """Конвертирует объект Prompt в сообщение OpenAI-совместимого формата.

    Сохраняет протокольные поля tool calling: у assistant-сообщений —
    tool_calls, у role="tool" — tool_call_id и name. Без этого история с
    вызовами инструментов становится невалидной для API (400 "missing field
    tool_call_id"), а стратегии контекстного окна теряют протокол при
    подготовке сообщений.
    """
    entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
    tool_calls = getattr(msg, "tool_calls", None)
    if msg.role == "assistant" and tool_calls:
        entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in tool_calls
        ]
    elif msg.role == "tool":
        tool_call_id = getattr(msg, "tool_call_id", None)
        if tool_call_id is not None:
            entry["tool_call_id"] = tool_call_id
        name = getattr(msg, "name", None)
        if name is not None:
            entry["name"] = name
    return entry


def group_tool_blocks(messages: list[Any]) -> list[list[Any]]:
    """Группирует сообщения так, чтобы группы assistant(tool_calls) + их
    tool-ответы оставались неделимыми.

    Это нужно стратегиям (скользящее окно, суммаризация), чтобы никогда не
    отрывать tool-ответы от соответствующего assistant-сообщения с tool_calls
    — иначе LLM получает невалидный протокол и отвечает ошибкой 400.
    """
    groups: list[list[Any]] = []
    current: list[Any] | None = None
    for msg in messages:
        if getattr(msg, "tool_calls", None):
            if current is not None:
                groups.append(current)
            current = [msg]
        elif msg.role == "tool" and current is not None:
            current.append(msg)
        else:
            if current is not None:
                groups.append(current)
                current = None
            groups.append([msg])
    if current is not None:
        groups.append(current)
    return groups


def align_group_boundary(groups: list[list[Any]], index: int) -> int:
    """Сдвигает границу среза назад на целую группу сообщений.

    Используется стратегиями: срез dialogue[:index] должен заканчиваться
    целиком на границе группы, чтобы assistant(tool_calls) не уходил в
    саммари, а его tool-ответы — в «хвост» (и наоборот).
    """
    remainder = 0
    for g in groups[index:]:
        remainder += len(g)
    return (
        max(0, min(index, len(groups) - 1))
        if not groups
        else _align_impl(groups, index, remainder)
    )


def _align_impl(groups: list[list[Any]], index: int, remainder: int) -> int:
    while index > 0 and remainder < len(groups[index - 1]):
        remainder += len(groups[index - 1])
        index -= 1
    return index


def align_window_start(messages: list[Any], offset: int) -> int:
    """Возвращает индекс начала окна, выровненный по целым группам.

    ``offset`` — желаемый индекс начала среза (len(messages) - window_size).
    Если внутри группы, граница сдвигается назад к началу группы.
    """
    if offset <= 0:
        return 0
    groups = group_tool_blocks(messages)
    aligned = 0
    for group in groups:
        if aligned >= offset:
            break
        aligned += len(group)
    return aligned


def sanitize_llm_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Приводит список сообщений к валидному протоколу tool calling.

    Убирает из запроса к LLM сообщения, которые ломают десериализацию на
    стороне API (например, YandexGPT возвращает 400 "missing field
    tool_call_id"):
      - assistant-сообщения с tool_calls, для которых не все tool-ответы
        присутствуют в истории (неполная группа — например, процесс был
        прерван между записью assistant и tool-сообщений);
      - tool-сообщения без корректной пары к assistant с tool_calls;
      - tool-вызовы, идущие раньше первого сообщения пользователя.
    """
    result: list[dict[str, Any]] = []
    i = 0
    n = len(messages)

    def has_user_before(start: int) -> bool:
        for m in messages[:start]:
            if m.get("role") == "user":
                return True
        return False

    while i < n:
        msg = messages[i]
        tool_calls = msg.get("tool_calls")
        if msg.get("role") == "assistant" and tool_calls:
            required = {tc.get("id") for tc in tool_calls}
            j = i + 1
            responses: list[dict[str, Any]] = []
            while j < n and messages[j].get("role") == "tool":
                responses.append(messages[j])
                j += 1
            responded = {r.get("tool_call_id") for r in responses}
            if required and required == responded and has_user_before(i):
                result.append(msg)
                result.extend(responses)
            else:
                # Неполная/некорректная группа — отбрасываем её целиком,
                # сохранив текстовый контент assistant как обычное сообщение.
                content = msg.get("content")
                if content and has_user_before(i):
                    result.append({"role": "assistant", "content": content})
            i = j
            continue
        if msg.get("role") == "tool":
            # Осиротевший tool-ответ (без предшествующего assistant с
            # tool_calls) — в запрос отправлять нельзя.
            i += 1
            continue
        result.append(msg)
        i += 1
    return result


class ContextWindowStrategy(ABC):
    """Абстрактный базовый класс для стратегий управления контекстным окном.

    Стратегия отвечает ТОЛЬКО за управление контекстным окном: какие
    диалоговые сообщения отправить в LLM и какое саммари к ним добавить.
    Подмешивание памяти, профиля и фазы — ответственность PromptBuilder.
    """

    @abstractmethod
    def apply(
        self,
        dialogue: list[Any],  # Список Prompt объектов (без system)
        llm_provider: LlmProvider | None = None,
    ) -> WindowResult:
        """Применяет стратегию к диалоговым сообщениям.

        Args:
            dialogue: Сообщения диалога в хронологическом порядке.
            llm_provider: Провайдер LLM для выполнения суммаризации.

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


class DefaultStrategy(ContextWindowStrategy):
    """
    Стратегия по умолчанию: простая пересылка всех сообщений.
    При переполнении контекстного окна выбрасывается исключение.
    """

    def apply(
        self,
        dialogue: list[Any],
        llm_provider: LlmProvider | None = None,
    ) -> WindowResult:
        """Возвращает все диалоговые сообщения как есть."""
        return WindowResult(dialogue=list(dialogue))

    def to_dict(self) -> dict[str, Any]:
        return {"strategy_type": self.strategy_type}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DefaultStrategy:
        return cls()

    @property
    def strategy_type(self) -> str:
        return "DefaultStrategy"


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

    @abstractmethod
    def _summarization_system_prompt(self) -> str:
        """Возвращает системный промпт для выполнения суммаризации."""

    def _summarization_kwargs(self) -> dict[str, Any]:
        """Дополнительные параметры запроса суммаризации."""
        return {}

    def apply(
        self,
        dialogue: list[Any],
        llm_provider: LlmProvider | None = None,
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
                    dialogue[:count], llm_provider
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
        messages_to_summarize: list[Any],
        llm_provider: LlmProvider,
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

        response = llm_provider.generate(
            messages=summarization_messages,
            temperature=0.3,
            max_tokens=500,
            **self._summarization_kwargs(),
        )

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


@dataclass
class SlidingWindowStrategy(ContextWindowStrategy):
    """
    Стратегия скользящего окна (Sliding Window).

    Параметры:
        window_size: Количество последних сообщений, которые передаются в LLM.

    Логика:
        - Для LLM отправляются только последние N сообщений.
        - Окно выравнивается по целым группам tool-вызовов.
        - История сохраняется полностью, но для LLM отправляется только окно.
    """

    window_size: int

    def __post_init__(self):
        if self.window_size <= 0:
            raise ValueError("window_size должен быть > 0")

    def apply(
        self,
        dialogue: list[Any],
        llm_provider: LlmProvider | None = None,
    ) -> WindowResult:
        """Возвращает последние window_size сообщений (с выравниванием)."""
        start = max(0, len(dialogue) - self.window_size)
        aligned_start = align_window_start(dialogue, start)
        return WindowResult(dialogue=dialogue[aligned_start:])

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_type": self.strategy_type,
            "window_size": self.window_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlidingWindowStrategy:
        return cls(window_size=data["window_size"])

    @property
    def strategy_type(self) -> str:
        return "SlidingWindowStrategy"


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
