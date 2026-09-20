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
        "ограничения": {"type": "string", "description": "Ограничения и требования к решению"},
        "предпочтения": {"type": "string", "description": "Предпочтения пользователя"},
        "решения": {"type": "string", "description": "Принятые решения и их обоснование"},
        "договоренности": {"type": "string", "description": "Достигнутые договоренности"}
    },
    "required": ["цель", "ограничения", "предпочтения", "решения", "договоренности"]
}


@dataclass
class PreparedMessages:
    """Результат подготовки сообщений для отправки в LLM."""
    messages: list[dict[str, Any]]
    summary: str | None = None  # Текущий саммари (если используется)
    is_summarization_request: bool = False  # Флаг: это запрос для суммаризации?
    summarization_tokens: tuple[int, int] | None = None  # (prompt_tokens, completion_tokens) от суммаризации


class ContextWindowStrategy(ABC):
    """Абстрактный базовый класс для стратегий управления контекстным окном."""

    @abstractmethod
    def prepare_messages(
        self,
        history: list[Any],  # Список Prompt объектов
        llm_provider: LlmProvider | None = None,
        agent_memory_text: str | None = None,  # Текст памяти о пользователе
    ) -> PreparedMessages:
        """
        Подготавливает сообщения для отправки в LLM провайдер.

        Args:
            history: Полная история сообщений (включая системный промпт).
            llm_provider: Провайдер LLM для выполнения суммаризации (если нужен).
            agent_memory_text: Текст памяти о пользователе (опционально).

        Returns:
            PreparedMessages: Сообщения для отправки в LLM и метаданные.
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

    def prepare_messages(
        self,
        history: list[Any],
        llm_provider: LlmProvider | None = None,
        agent_memory_text: str | None = None,
    ) -> PreparedMessages:
        """Просто возвращает все сообщения как есть."""
        messages = []
        for msg in history:
            msg_dict: dict[str, Any] = {"role": msg.role, "content": msg.content}
            messages.append(msg_dict)

        # Добавляем память о пользователе если есть
        if agent_memory_text and messages and messages[0]["role"] == "system":
            messages[0]["content"] = f"{messages[0]['content']}\n\n{agent_memory_text}"
        elif agent_memory_text:
            messages.insert(0, {"role": "system", "content": agent_memory_text})

        return PreparedMessages(messages=messages)

    def to_dict(self) -> dict[str, Any]:
        return {"strategy_type": self.strategy_type}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DefaultStrategy:
        return cls()

    @property
    def strategy_type(self) -> str:
        return "DefaultStrategy"


@dataclass
class SummarizationStrategy(ContextWindowStrategy):
    """
    Стратегия с суммаризацией истории.

    Параметры:
        non_compressible_count: Количество последних сообщений, которые не сжимаются.
        buffer_size: Размер буфера сообщений перед суммаризацией.

    Логика:
        - Системный промпт не считается и не суммаризируется.
        - После добавления (non_compressible_count + buffer_size) сообщений,
          первые buffer_size сообщений суммаризируются.
        - Саммари хранится в поле стратегии и передаётся при следующей суммаризации.
        - История сохраняется полностью, суммаризация только для отправки в LLM.
    """

    non_compressible_count: int
    buffer_size: int
    _summary: str | None = field(default=None, repr=False)  # Хранит текущий саммари

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

    def prepare_messages(
        self,
        history: list[Any],
        llm_provider: LlmProvider | None = None,
        agent_memory_text: str | None = None,
    ) -> PreparedMessages:
        """
        Подготавливает сообщения для отправки в LLM.

        Если требуется суммаризация, выполняет её и возвращает сообщения с саммари.
        """
        # Разделяем системный промпт и остальные сообщения
        system_msg = None
        other_messages = []
        for msg in history:
            if msg.role == "system":
                system_msg = msg
            else:
                other_messages.append(msg)

        # Проверяем, нужна ли суммаризация
        total_other = len(other_messages)
        threshold = self.non_compressible_count + self.buffer_size

        # Суммаризация нужна, когда количество сообщений достигает порога
        # и есть сообщения для суммаризации (кратные buffer_size)
        if total_other >= threshold and llm_provider is not None:
            # Вычисляем, сколько сообщений нужно просуммировать
            # Это все сообщения кроме последних non_compressible_count, округленные вниз до кратных buffer_size
            messages_to_summarize_count = total_other - self.non_compressible_count
            messages_to_summarize_count = (messages_to_summarize_count // self.buffer_size) * self.buffer_size

            if messages_to_summarize_count > 0:
                messages_to_summarize = other_messages[:messages_to_summarize_count]
                remaining_messages = other_messages[messages_to_summarize_count:]

                # Выполняем суммаризацию
                new_summary, tech_tokens = self._perform_summarization(
                    messages_to_summarize,
                    llm_provider,
                )
                self._summary = new_summary

                # Формируем итоговые сообщения
                result_messages = []
                if system_msg:
                    result_messages.append({"role": "system", "content": system_msg.content})

                # Добавляем саммари как системное сообщение (или как часть промпта)
                if new_summary:
                    result_messages.append({"role": "system", "content": f"История диалога: {new_summary}"})

                # Добавляем оставшиеся сообщения
                for msg in remaining_messages:
                    result_messages.append({"role": msg.role, "content": msg.content})

                return PreparedMessages(
                    messages=result_messages,
                    summary=new_summary,
                    is_summarization_request=False,  # Основной запрос не технический
                    summarization_tokens=tech_tokens,
                )

        # Суммаризация не требуется, возвращаем все сообщения как есть
        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg.content})

        # Добавляем существующий саммари если есть
        if self._summary:
            messages.append({"role": "system", "content": f"История диалога: {self._summary}"})

        for msg in other_messages:
            messages.append({"role": msg.role, "content": msg.content})

        # Добавляем память о пользователе если есть
        if agent_memory_text and messages and messages[0]["role"] == "system":
            messages[0]["content"] = f"{messages[0]['content']}\n\n{agent_memory_text}"
        elif agent_memory_text:
            messages.insert(0, {"role": "system", "content": agent_memory_text})

        return PreparedMessages(
            messages=messages,
            summary=self._summary,
            is_summarization_request=False,
        )

    def _perform_summarization(
        self,
        messages_to_summarize: list[Any],
        llm_provider: LlmProvider,
    ) -> tuple[str, tuple[int, int]]:
        """
        Выполняет суммаризацию указанных сообщений через LLM.

        Args:
            messages_to_summarize: Сообщения для суммаризации.
            llm_provider: Провайдер LLM.

        Returns:
            Кортеж (саммари, (prompt_tokens, completion_tokens)).
        """
        print("\n[INFO] Запущена суммаризация...")

        # Формируем системный промпт для суммаризации
        system_prompt = (
            "Ты ассистент для суммаризации диалогов. "
            "Твоя задача — создать максимально краткое содержание предоставленной истории переписки. "
            "Включи только ключевые моменты: предпочтения пользователя, ограничения задачи и важные выводы. "
            "Не тяни бездумно все данные, а выделяй только существенную информацию. "
            "Если есть предыдущее саммари, объедини его с новыми сообщениями, сохраняя краткость."
        )

        # Формируем сообщения для суммаризации
        summarization_messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Добавляем предыдущий саммари если есть
        if self._summary:
            summarization_messages.append(
                {"role": "user", "content": f"Предыдущее саммари: {self._summary}"}
            )

        # Добавляем сообщения для суммаризации
        for msg in messages_to_summarize:
            role = msg.role
            content = msg.content
            summarization_messages.append({"role": role, "content": content})

        # Делаем запрос к LLM
        response = llm_provider.generate(
            messages=summarization_messages,
            temperature=0.3,
            max_tokens=500,
        )

        # Возвращаем саммари и токены
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
    def from_dict(cls, data: dict[str, Any]) -> SummarizationStrategy:
        instance = cls(
            non_compressible_count=data["non_compressible_count"],
            buffer_size=data["buffer_size"],
        )
        instance._summary = data.get("summary")
        return instance

    @property
    def strategy_type(self) -> str:
        return "SummarizationStrategy"


@dataclass
class KeyValueMemoryStrategy(ContextWindowStrategy):
    """
    Стратегия с суммаризацией истории в формате JSON (Key-Value Memory).

    Параметры:
        non_compressible_count: Количество последних сообщений, которые не сжимаются.
        buffer_size: Размер буфера сообщений перед суммаризацией.

    Логика:
        - Системный промпт не считается и не суммаризируется.
        - После добавления (non_compressible_count + buffer_size) сообщений,
          первые buffer_size сообщений суммаризируются.
        - Саммари хранится в поле стратегии в виде JSON со строгой схемой:
          ключи: цель, ограничения, предпочтения, решения, договоренности.
        - История сохраняется полностью, суммаризация только для отправки в LLM.
    """

    non_compressible_count: int
    buffer_size: int
    _summary: str | None = field(default=None, repr=False)  # Хранит текущий саммари в формате JSON

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

    def prepare_messages(
        self,
        history: list[Any],
        llm_provider: LlmProvider | None = None,
        agent_memory_text: str | None = None,
    ) -> PreparedMessages:
        """
        Подготавливает сообщения для отправки в LLM.

        Если требуется суммаризация, выполняет её и возвращает сообщения с саммари.
        """
        # Разделяем системный промпт и остальные сообщения
        system_msg = None
        other_messages = []
        for msg in history:
            if msg.role == "system":
                system_msg = msg
            else:
                other_messages.append(msg)

        # Проверяем, нужна ли суммаризация
        total_other = len(other_messages)
        threshold = self.non_compressible_count + self.buffer_size

        # Суммаризация нужна, когда количество сообщений достигает порога
        # и есть сообщения для суммаризации (кратные buffer_size)
        if total_other >= threshold and llm_provider is not None:
            # Вычисляем, сколько сообщений нужно просуммировать
            # Это все сообщения кроме последних non_compressible_count, округленные вниз до кратных buffer_size
            messages_to_summarize_count = total_other - self.non_compressible_count
            messages_to_summarize_count = (messages_to_summarize_count // self.buffer_size) * self.buffer_size

            if messages_to_summarize_count > 0:
                messages_to_summarize = other_messages[:messages_to_summarize_count]
                remaining_messages = other_messages[messages_to_summarize_count:]

                # Выполняем суммаризацию
                new_summary, tech_tokens = self._perform_summarization(
                    messages_to_summarize,
                    llm_provider,
                )
                self._summary = new_summary

                # Формируем итоговые сообщения
                result_messages = []
                if system_msg:
                    result_messages.append({"role": "system", "content": system_msg.content})

                # Добавляем саммари как системное сообщение (или как часть промпта)
                if new_summary:
                    result_messages.append({"role": "system", "content": f"История диалога: {new_summary}"})

                # Добавляем память о пользователе если есть
                if agent_memory_text:
                    result_messages.append({"role": "system", "content": agent_memory_text})

                # Добавляем оставшиеся сообщения
                for msg in remaining_messages:
                    result_messages.append({"role": msg.role, "content": msg.content})

                return PreparedMessages(
                    messages=result_messages,
                    summary=new_summary,
                    is_summarization_request=False,  # Основной запрос не технический
                    summarization_tokens=tech_tokens,
                )

        # Суммаризация не требуется, возвращаем все сообщения как есть
        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg.content})

        # Добавляем существующий саммари если есть
        if self._summary:
            messages.append({"role": "system", "content": f"История диалога: {self._summary}"})

        # Добавляем память о пользователе если есть
        if agent_memory_text:
            messages.append({"role": "system", "content": agent_memory_text})

        for msg in other_messages:
            messages.append({"role": msg.role, "content": msg.content})

        return PreparedMessages(
            messages=messages,
            summary=self._summary,
            is_summarization_request=False,
        )

    def _perform_summarization(
        self,
        messages_to_summarize: list[Any],
        llm_provider: LlmProvider,
    ) -> tuple[str, tuple[int, int]]:
        """
        Выполняет суммаризацию указанных сообщений через LLM.

        Args:
            messages_to_summarize: Сообщения для суммаризации.
            llm_provider: Провайдер LLM.

        Returns:
            Кортеж (саммари, (prompt_tokens, completion_tokens)).
        """
        print("\n[INFO] Запущена суммаризация (Key-Value Memory)...")

        # Формируем системный промпт для суммаризации с указанием JSON схемы
        system_prompt = (
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

        # Формируем сообщения для суммаризации
        summarization_messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Добавляем предыдущий саммари если есть
        if self._summary:
            summarization_messages.append(
                {"role": "user", "content": f"Предыдущее саммари: {self._summary}"}
            )

        # Добавляем сообщения для суммаризации
        for msg in messages_to_summarize:
            role = msg.role
            content = msg.content
            summarization_messages.append({"role": role, "content": content})

        # Делаем запрос к LLM с response_format для гарантии JSON
        response = llm_provider.generate(
            messages=summarization_messages,
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        # Возвращаем саммари и токены
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
    def from_dict(cls, data: dict[str, Any]) -> KeyValueMemoryStrategy:
        instance = cls(
            non_compressible_count=data["non_compressible_count"],
            buffer_size=data["buffer_size"],
        )
        instance._summary = data.get("summary")
        return instance

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
        - При каждом запросе передаётся системный промпт (если есть) + N последних сообщений.
        - Все сообщения старше N не передаются в LLM.
        - История сохраняется полностью в хранилище, но для LLM отправляются только последние N сообщений.
    """

    window_size: int

    def __post_init__(self):
        if self.window_size <= 0:
            raise ValueError("window_size должен быть > 0")

    def prepare_messages(
        self,
        history: list[Any],
        llm_provider: LlmProvider | None = None,
        agent_memory_text: str | None = None,
    ) -> PreparedMessages:
        """
        Подготавливает сообщения для отправки в LLM.

        Возвращает системный промпт + последние window_size сообщений.
        """
        # Разделяем системный промпт и остальные сообщения
        system_msg = None
        other_messages = []
        for msg in history:
            if msg.role == "system":
                system_msg = msg
            else:
                other_messages.append(msg)

        # Берём только последние window_size сообщений
        recent_messages = other_messages[-self.window_size:] if self.window_size < len(other_messages) else other_messages

        # Формируем итоговые сообщения
        messages = []
        if system_msg:
            messages.append({"role": "system", "content": system_msg.content})

        # Добавляем память о пользователе если есть
        if agent_memory_text:
            messages.append({"role": "system", "content": agent_memory_text})

        for msg in recent_messages:
            messages.append({"role": msg.role, "content": msg.content})

        return PreparedMessages(
            messages=messages,
            summary=None,
            is_summarization_request=False,
        )

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
