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
    last_message_preview: str | None = None


class Agent:
    """Агент для ведения диалога с пользователем через LLM."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        history_storage: Any | None = None,
        messages: list[Prompt] | None = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self._llm_provider = llm_provider
        self._settings = initial_settings or AgentSettings()
        self._messages: list[Prompt] = messages if messages is not None else []
        self._history_storage = history_storage

        # Добавляем системный промпт только если сообщений ещё нет
        if system_prompt and not self._messages:
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
