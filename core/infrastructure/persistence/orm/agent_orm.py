from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.domain.dtos.agent_settings import AgentSettings
from core.domain.entities.agent_phase import AgentPhase
from core.infrastructure.persistence.orm.base import Base
from core.infrastructure.persistence.orm.serialization import (
    _deserialize_phase,
    _deserialize_settings,
    _serialize_phase,
    _serialize_settings,
)

if TYPE_CHECKING:
    from core.infrastructure.persistence.orm.agent_knowledge_base_orm import (
        AgentKnowledgeBaseORM,
    )
    from core.infrastructure.persistence.orm.task_profile_orm import TaskProfileORM


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
        is_dialog_remembered: Флаг сохранения диалога в глобальную память.
        settings_json: JSON сериализованные настройки агента (model_id, temperature и т.д.).
        strategy_type: Тип стратегии управления контекстным окном.
        strategy_params_json: JSON параметры стратегии.
        chat_prompt_tokens: Сумма prompt_tokens без технических запросов.
        chat_completion_tokens: Сумма completion_tokens без технических запросов.
        tech_prompt_tokens: Сумма prompt_tokens технических запросов (суммаризация).
        tech_completion_tokens: Сумма completion_tokens технических запросов.
        current_phase: Текущая фаза работы агента (plan, execute, validate, report).
    """

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_message_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_dialog_remembered: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="DefaultStrategy"
    )
    strategy_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    chat_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chat_completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    tech_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tech_completion_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    # Ходы с последнего обновления памяти задачи диалога (per-chat каденция)
    turns_since_task_memory: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    current_phase: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="plan"
    )
    # JSON-список машинных имён подключённых к чату MCP-серверов (по умолчанию пусто)
    mcp_servers_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign key to TaskProfile (optional, set only at creation)
    task_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_profiles.id"), nullable=True
    )

    # Relationship back to TaskProfile
    task_profile: Mapped[TaskProfileORM | None] = relationship(back_populates="agents")

    # Связи с базами знаний (RAG)
    knowledge_base_links: Mapped[list[AgentKnowledgeBaseORM]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

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

    def get_current_phase(self) -> AgentPhase | None:
        """Возвращает текущую фазу агента."""
        return _deserialize_phase(self.current_phase)

    def set_current_phase(self, phase: AgentPhase | None) -> None:
        """Устанавливает текущую фазу агента."""
        self.current_phase = _serialize_phase(phase)

    def get_mcp_servers(self) -> list[str]:
        """Возвращает список машинных имён подключённых MCP-серверов."""
        if not self.mcp_servers_json:
            return []
        try:
            data = json.loads(self.mcp_servers_json)
        except (json.JSONDecodeError, TypeError):
            return []
        return [str(name) for name in data] if isinstance(data, list) else []

    def set_mcp_servers(self, servers: list[str] | None) -> None:
        """Сохраняет список подключённых MCP-серверов."""
        if not servers:
            self.mcp_servers_json = None
        else:
            self.mcp_servers_json = json.dumps(list(servers))

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
