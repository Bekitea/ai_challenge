import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agents import AgentSettings


class Base(DeclarativeBase):
    """Базовый класс для всех ORM моделей."""


def _serialize_settings(settings: AgentSettings | None) -> str | None:
    """Сериализует AgentSettings в JSON строку."""
    if settings is None:
        return None
    return json.dumps(settings.to_dict())


def _deserialize_settings(json_str: str | None) -> AgentSettings | None:
    """Десериализует JSON строку в AgentSettings."""
    if json_str is None:
        return None
    data = json.loads(json_str)
    return AgentSettings(**data)


class AgentORM(Base):
    """
    ORM модель для хранения метаданных агента.

    Атрибуты:
        id: Числовой ID агента (primary key), отображается пользователю.
        conversation_id: UUID для связи с историей переписки в файловом хранилище.
        name: Название агента/чата.
        last_message_timestamp: Время последнего сообщения (для сортировки).
        message_count: Количество сообщений в диалоге (без системного промпта).
        last_message_preview: Превью последнего сообщения (первые 50 символов).
        system_prompt: Системный промпт (хранится в БД, так как это настройка).
        settings_json: JSON сериализованные настройки агента (model_id, temperature и т.д.).
        strategy_type: Тип стратегии управления контекстным окном.
        strategy_params_json: JSON параметры стратегии.
        chat_prompt_tokens: Сумма prompt_tokens без технических запросов.
        chat_completion_tokens: Сумма completion_tokens без технических запросов.
        tech_prompt_tokens: Сумма prompt_tokens технических запросов (суммаризация).
        tech_completion_tokens: Сумма completion_tokens технических запросов.
    """
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_message_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(String(100), nullable=True, default="DefaultStrategy")
    strategy_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chat_completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tech_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tech_completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def get_settings(self) -> AgentSettings | None:
        """Возвращает десериализованные настройки агента."""
        return _deserialize_settings(self.settings_json)

    def set_settings(self, settings: AgentSettings | None) -> None:
        """Сериализует и сохраняет настройки агента."""
        self.settings_json = _serialize_settings(settings)

    def get_strategy_params(self) -> dict | None:
        """Возвращает десериализованные параметры стратегии."""
        if self.strategy_params_json is None:
            return None
        return json.loads(self.strategy_params_json)

    def set_strategy_params(self, params: dict | None) -> None:
        """Сериализует и сохраняет параметры стратегии."""
        if params is None:
            self.strategy_params_json = None
        else:
            self.strategy_params_json = json.dumps(params)

    @property
    def total_prompt_tokens(self) -> int:
        """Возвращает общее количество prompt_tokens (чат + технические)."""
        return self.chat_prompt_tokens + self.tech_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Возвращает общее количество completion_tokens (чат + технические)."""
        return self.chat_completion_tokens + self.tech_completion_tokens

    def __repr__(self) -> str:
        return f"<AgentORM(id={self.id}, name={self.name})>"
