import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from llm_providers import LlmProvider, LlmResponse


@dataclass
class AgentSettings:
    """Настройки агента для взаимодействия с LLM."""

    model_id: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None

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
            }.items()
            if v is not None
        }


@dataclass
class Prompt:
    """Сообщение в диалоге с агентом."""

    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime | None = None  # None для system, обязательно для user и assistant
    reasoning: str | None = None  # Только для assistant
    settings: AgentSettings | None = None  # Только для assistant (настройки на момент генерации)


@dataclass
class AgentPreview:
    """Превью агента для отображения в списке."""

    agent_id: str
    name: str
    last_message_timestamp: datetime | None
    message_count: int


class Agent:
    """Агент для ведения диалога с пользователем через LLM."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self._llm_provider = llm_provider
        self._settings = initial_settings or AgentSettings()
        self._messages: list[Prompt] = []

        if system_prompt:
            self._messages.append(Prompt(role="system", content=system_prompt))

        self._last_message_timestamp: datetime | None = None

    def get_settings(self) -> AgentSettings:
        """Возвращает текущие настройки агента."""
        return self._settings

    def update_settings(self, new_settings: AgentSettings) -> None:
        """Обновляет настройки агента."""
        self._settings = new_settings

    def get_history(self) -> list[Prompt]:
        """Возвращает всю историю диалога (включая системный промпт)."""
        return self._messages.copy()

    def get_messages_for_display(self) -> list[Prompt]:
        """Возвращает сообщения для отображения пользователю (без системного промпта)."""
        return [msg for msg in self._messages if msg.role != "system"]

    def continue_dialog(self, user_prompt: str) -> LlmResponse:
        """
        Продолжает диалог: добавляет сообщение пользователя, делает запрос к LLM,
        сохраняет ответ и возвращает результат.

        Args:
            user_prompt: Текст сообщения от пользователя.

        Returns:
            LlmResponse: Ответ от LLM с контентом и reasoning.
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

        # Формируем messages для отправки в LLM
        messages_for_llm = []
        for msg in self._messages:
            msg_dict: dict[str, Any] = {"role": msg.role, "content": msg.content}
            messages_for_llm.append(msg_dict)

        # Получаем текущие настройки
        settings = self._settings
        kwargs = settings.to_dict()

        # Делаем запрос к LLM
        response = self._llm_provider.generate(messages=messages_for_llm, **kwargs)

        # Сохраняем ответ ассистента
        assistant_timestamp = datetime.now()
        assistant_message = Prompt(
            role="assistant",
            content=response.content,
            timestamp=assistant_timestamp,
            reasoning=response.reasoning,
            settings=AgentSettings(
                model_id=settings.model_id,
                top_k=settings.top_k,
                top_p=settings.top_p,
                temperature=settings.temperature,
                reasoning_effort=settings.reasoning_effort,
            ),
        )
        self._messages.append(assistant_message)
        self._last_message_timestamp = assistant_timestamp

        return response

    @property
    def last_message_timestamp(self) -> datetime | None:
        """Возвращает временную метку последнего сообщения."""
        return self._last_message_timestamp

    @property
    def message_count(self) -> int:
        """Возвращает количество сообщений (без системного промпта)."""
        return len([msg for msg in self._messages if msg.role != "system"])


class AgentRepository(ABC):
    """Абстракция для хранения и управления агентами."""

    @abstractmethod
    def create_agent(
        self,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента с уникальным идентификатором.

        Args:
            name: Название агента.
            llm_provider: Провайдер LLM для запросов.
            initial_settings: Начальные настройки агента.
            system_prompt: Системный промпт (опционально).

        Returns:
            Agent: Newly created agent instance.
        """

    @abstractmethod
    def get_agent(self, agent_id: str) -> Agent | None:
        """
        Получает агента по идентификатору.

        Args:
            agent_id: Уникальный идентификатор агента.

        Returns:
            Agent или None, если агент не найден.
        """

    @abstractmethod
    def get_all_previews(self) -> list[AgentPreview]:
        """
        Получает превью всех агентов, отсортированные по дате последнего сообщения
        (последние сверху).

        Returns:
            Список AgentPreview, отсортированный по last_message_timestamp (descending).
        """


class InMemoryAgentRepository(AgentRepository):
    """Реализация AgentRepository с хранением в памяти."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def create_agent(
        self,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
    ) -> Agent:
        agent_id = str(uuid.uuid4())
        agent = Agent(
            agent_id=agent_id,
            name=name,
            llm_provider=llm_provider,
            initial_settings=initial_settings,
            system_prompt=system_prompt,
        )
        self._agents[agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def get_all_previews(self) -> list[AgentPreview]:
        previews = [
            AgentPreview(
                agent_id=agent.agent_id,
                name=agent.name,
                last_message_timestamp=agent.last_message_timestamp,
                message_count=agent.message_count,
            )
            for agent in self._agents.values()
        ]
        # Сортировка по last_message_timestamp descending (None в конце)
        previews.sort(
            key=lambda p: p.last_message_timestamp if p.last_message_timestamp else datetime.min,
            reverse=True,
        )
        return previews
