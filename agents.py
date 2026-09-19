from dataclasses import dataclass
from datetime import datetime
from typing import Any

from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
)
from llm_providers import LlmProvider, LlmResponse


class ContextWindowExceededError(Exception):
    """Исключение, выбрасываемое при превышении лимита контекстного окна."""


@dataclass
class AgentSettings:
    """Настройки агента для взаимодействия с LLM."""

    model_id: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения."""
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "reasoning_effort": self.reasoning_effort,
                "context_window_size": self.context_window_size,
            }.items()
            if v is not None
        }

    def to_llm_request_properties(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения."""
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "reasoning_effort": self.reasoning_effort,
            }.items()
            if v is not None
        }


@dataclass
class TokenCounters:
    """Счетчики токенов для чата."""

    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    tech_prompt_tokens: int = 0
    tech_completion_tokens: int = 0

    @property
    def total_prompt_tokens(self) -> int:
        """Общее количество prompt_tokens."""
        return self.chat_prompt_tokens + self.tech_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Общее количество completion_tokens."""
        return self.chat_completion_tokens + self.tech_completion_tokens


@dataclass
class Prompt:
    """Сообщение в диалоге с агентом."""

    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime | None = (
        None  # None для system, обязательно для user и assistant
    )
    reasoning: str | None = None  # Только для assistant
    settings: AgentSettings | None = (
        None  # Только для assistant (настройки на момент генерации)
    )
    prompt_tokens: int | None = None  # Только для assistant
    completion_tokens: int | None = None  # Только для assistant


@dataclass
class AgentPreview:
    """Превью агента для отображения в списке."""

    agent_id: int
    name: str
    last_message_timestamp: datetime | None
    message_count: int
    last_message_preview: str | None = None


class Agent:
    """Агент для ведения диалога с пользователем через LLM."""

    def __init__(
        self,
        agent_id: int | None,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        history_storage: Any | None = None,
        messages: list[Prompt] | None = None,
        strategy: ContextWindowStrategy | None = None,
        auto_save: bool = True,
        conversation_id: str | None = None,
    ):
        self.agent_id = agent_id
        self.conversation_id = conversation_id  # UUID для связи с файловым хранилищем
        self.name = name
        self._llm_provider = llm_provider
        self._settings = initial_settings or AgentSettings()
        self._messages: list[Prompt] = messages if messages is not None else []
        self._history_storage = history_storage
        self._strategy = strategy or DefaultStrategy()
        self._auto_save = auto_save
        self._repository = None  # Устанавливается при регистрации в репозитории

        # Добавляем системный промпт только если сообщений ещё нет
        if system_prompt and not self._messages:
            self._messages.append(Prompt(role="system", content=system_prompt))

        self._last_message_timestamp: datetime | None = None
        self._token_counters = TokenCounters()

    @property
    def token_counters(self) -> TokenCounters:
        """Возвращает счетчики токенов."""
        return self._token_counters

    @property
    def strategy(self) -> ContextWindowStrategy:
        """Возвращает стратегию управления контекстным окном."""
        return self._strategy

    def set_strategy(self, strategy: ContextWindowStrategy) -> None:
        """Устанавливает стратегию управления контекстным окном."""
        self._strategy = strategy

    def get_settings(self) -> AgentSettings:
        """Возвращает текущие настройки агента."""
        return self._settings

    def update_settings(self, new_settings: AgentSettings) -> None:
        """Обновляет настройки агента."""
        self._settings = new_settings
        if self._repository is not None and self._auto_save:
            self.save()

    def get_history(self) -> list[Prompt]:
        """Возвращает всю историю диалога (включая системный промпт)."""
        return self._messages.copy()

    def save(self) -> None:
        """
        Сохраняет текущее состояние агента.

        Если агент зарегистрирован в репозитории и включен auto_save,
        сохраняет метаданные и историю через репозиторий.
        """
        if self._repository is not None and self._auto_save:
            self._repository.update_agent(self)

    def continue_dialog(self, user_prompt: str) -> LlmResponse:
        """
        Продолжает диалог: добавляет сообщение пользователя, делает запрос к LLM,
        сохраняет ответ и возвращает результат.

        Args:
            user_prompt: Текст сообщения от пользователя.

        Returns:
            LlmResponse: Ответ от LLM с контентом и reasoning.

        Raises:
            ContextWindowExceededError: Если prompt_tokens превысил размер контекстного окна.
        """
        # Добавляем сообщение пользователя
        user_timestamp = datetime.now()
        user_message = Prompt(
            role="user",
            content=user_prompt,
            timestamp=user_timestamp,
        )
        self._messages.append(user_message)
        self._last_message_timestamp = user_timestamp

        # Подготавливаем сообщения через стратегию
        prepared = self._strategy.prepare_messages(
            history=self._messages,
            llm_provider=self._llm_provider,
        )
        messages_for_llm = prepared.messages

        settings = self._settings
        kwargs = settings.to_llm_request_properties()

        # Делаем запрос к LLM
        response = self._llm_provider.generate(messages=messages_for_llm, **kwargs)

        # Проверяем лимит контекстного окна (только для assistant prompt)
        context_window_size = (
            settings.context_window_size or 200_000
        )  # По умолчанию 200k
        if (
            response.prompt_tokens is not None
            and response.prompt_tokens > context_window_size
        ):
            raise ContextWindowExceededError(
                f"Превышен лимит контекстного окна: {response.prompt_tokens} токенов (лимит: {context_window_size})"
            )

        # Обновляем счетчики токенов
        # Сначала обновляем счетчики от суммаризации (если была)
        if prepared.summarization_tokens:
            tech_prompt, tech_completion = prepared.summarization_tokens
            self._token_counters.tech_prompt_tokens += tech_prompt
            self._token_counters.tech_completion_tokens += tech_completion

        # Затем обновляем счетчики от основного запроса
        is_tech_request = prepared.is_summarization_request
        if response.prompt_tokens is not None:
            if is_tech_request:
                self._token_counters.tech_prompt_tokens += response.prompt_tokens
            else:
                self._token_counters.chat_prompt_tokens += response.prompt_tokens

        if response.completion_tokens is not None:
            if is_tech_request:
                self._token_counters.tech_completion_tokens += (
                    response.completion_tokens
                )
            else:
                self._token_counters.chat_completion_tokens += (
                    response.completion_tokens
                )

        # Сохраняем ответ ассистента
        assistant_timestamp = datetime.now()
        assistant_message = Prompt(
            role="assistant",
            content=response.content,
            timestamp=assistant_timestamp,
            reasoning=response.reasoning,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            settings=AgentSettings(
                model_id=settings.model_id,
                top_k=settings.top_k,
                top_p=settings.top_p,
                temperature=settings.temperature,
                reasoning_effort=settings.reasoning_effort,
                context_window_size=settings.context_window_size,
            ),
        )
        self._messages.append(assistant_message)
        self._last_message_timestamp = assistant_timestamp

        # Автосохранение после каждого сообщения
        if self._auto_save:
            self.save()

        return response

    @property
    def last_message_timestamp(self) -> datetime | None:
        """Возвращает временную метку последнего сообщения."""
        return self._last_message_timestamp

    @property
    def message_count(self) -> int:
        """Возвращает количество сообщений (без системного промпта)."""
        return len([msg for msg in self._messages if msg.role != "system"])

    def get_last_message_preview(self, max_length: int = 50) -> str | None:
        """Возвращает превью последнего сообщения пользователя или агента."""
        non_system_messages = [msg for msg in self._messages if msg.role != "system"]
        if not non_system_messages:
            return None

        last_msg = non_system_messages[-1]
        preview = last_msg.content[:max_length]
        if len(last_msg.content) > max_length:
            preview += "..."
        return preview

    def branch(
        self,
        new_name: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента-ветку на основе текущего.

        Копируются настройки, вся история сообщений, счетчики токенов и стратегия.
        Ветка получает новый conversation_id (UUID) для отдельного хранения истории.

        Args:
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """
        from datetime import datetime
        from uuid import uuid4

        from context_strategies import create_strategy_from_dict

        # Новый агент создается без ID - он будет установлен при сохранении в репозиторий
        if not new_name:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_name = f"{self.name} (branch {timestamp})"

        current_settings = self.get_settings()
        current_history = self.get_history()

        current_strategy = self.strategy
        strategy_dict = current_strategy.to_dict()
        new_strategy = create_strategy_from_dict(strategy_dict)

        branched_agent = Agent(
            agent_id=None,
            conversation_id=str(uuid4()),  # Новый UUID для ветки
            name=new_name,
            llm_provider=self._llm_provider,
            initial_settings=current_settings,
            system_prompt=None,
            history_storage=self._history_storage,
            messages=current_history.copy(),
            strategy=new_strategy,
            auto_save=True,
        )

        branched_agent._repository = self._repository

        current_counters = self.token_counters
        branched_agent._token_counters.chat_prompt_tokens = (
            current_counters.chat_prompt_tokens
        )
        branched_agent._token_counters.chat_completion_tokens = (
            current_counters.chat_completion_tokens
        )
        branched_agent._token_counters.tech_prompt_tokens = (
            current_counters.tech_prompt_tokens
        )
        branched_agent._token_counters.tech_completion_tokens = (
            current_counters.tech_completion_tokens
        )

        if current_history:
            non_system_msgs = [m for m in current_history if m.role != "system"]
            if non_system_msgs:
                branched_agent._last_message_timestamp = non_system_msgs[-1].timestamp

        if self._repository is not None:
            self._repository.update_agent(branched_agent)

        return branched_agent
