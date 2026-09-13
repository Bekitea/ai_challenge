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
        id: UUID агента (primary key).
        name: Название агента/чата.
        last_message_timestamp: Время последнего сообщения (для сортировки).
        message_count: Количество сообщений в диалоге (без системного промпта).
        last_message_preview: Превью последнего сообщения (первые 50 символов).
        system_prompt: Системный промпт (хранится в БД, так как это настройка).
        settings_json: JSON сериализованные настройки агента (model_id, temperature и т.д.).
    """
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_message_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def get_settings(self) -> AgentSettings | None:
        """Возвращает десериализованные настройки агента."""
        return _deserialize_settings(self.settings_json)

    def set_settings(self, settings: AgentSettings | None) -> None:
        """Сериализует и сохраняет настройки агента."""
        self.settings_json = _serialize_settings(settings)

    def __repr__(self) -> str:
        return f"<AgentORM(id={self.id}, name={self.name})>"
