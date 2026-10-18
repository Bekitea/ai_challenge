"""Pydantic-схемы REST API и маппинг DTO use cases -> схема.

Схемы повторяют DTO из ``use_cases`` (и RAG-DTO из ``rag_models``). Все
модели сконфигурированы на ``from_attributes=True``, поэтому dataclass-DTO
преобразуются напрямую через ``Model.model_validate(dto)``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Базовая схема: конфигурация чтения из dataclass-DTO."""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Выходные DTO
# ---------------------------------------------------------------------------


class AvailableModel(_Base):
    """Доступная модель с указанием провайдера."""

    provider: str
    model_id: str
    display_name: str


class ChatPreview(_Base):
    """Превью чата для списка."""

    agent_id: int
    name: str
    last_message_timestamp: datetime | None = None
    message_count: int
    last_message_preview: str | None = None


class Chat(_Base):
    """Базовые атрибуты чата."""

    agent_id: int
    name: str
    strategy_type: str
    current_phase: str
    system_prompt: str | None = None
    task_profile_name: str | None = None


class TaskMemory(_Base):
    """Память задачи текущего диалога."""

    goal: str = ""
    constraints: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    clarifications: list[str] = Field(default_factory=list)


class ChatInfo(_Base):
    """Информация о чате и счётчики токенов."""

    name: str
    agent_id: int
    strategy_type: str
    message_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    has_summary: bool = False
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    task_profile_name: str | None = None
    current_phase: str | None = None
    task_memory: TaskMemory | None = None


class Settings(_Base):
    """Настройки чата (используются и на вход, и на выход)."""

    model_id: str | None = None
    provider: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None
    reranker_enabled: bool = True


class HistoryMessage(_Base):
    """Одно сообщение истории диалога."""

    role: str
    content: str
    reasoning: str | None = None
    has_tool_calls: bool = False
    timestamp: datetime | None = None


class RagSource(_Base):
    """Источник RAG в ответе ассистента."""

    document_name: str
    chunk_id: int
    chunk_index: int
    text: str
    relevance: float | None = None


class MessageResponse(_Base):
    """Ответ ассистента на сообщение."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    context_window_size: int | None = None
    rag_sources: list[RagSource] | None = None


class CommandResponse(_Base):
    """Результат ассистентской команды (/help, /support, /files).

    ``messages`` — информационные сообщения о подготовке контекста (БЗ, MCP);
    ``response`` — ответ агента или ``None``, если вопрос не задан.
    """

    messages: list[str] = Field(default_factory=list)
    response: MessageResponse | None = None


class McpServerStatus(_Base):
    """Статус MCP-сервера в контексте чата."""

    name: str
    title: str
    description: str
    connected: bool
    tools: list[str] = Field(default_factory=list)


class AvailableMcpServer(_Base):
    """MCP-сервер из реестра, доступный для подключения."""

    name: str
    title: str
    description: str


class ActionResult(_Base):
    """Универсальный результат операции (успех + сообщение)."""

    success: bool
    message: str | None = None


class PhaseChangeResult(_Base):
    """Результат команды перехода по фазам."""

    success: bool
    message: str
    current_phase: str


class Invariant(_Base):
    """Инвариант профиля задачи."""

    id: int
    text: str
    created_at: datetime


class TaskProfile(_Base):
    """Информация о профиле задачи."""

    id: str
    name: str
    description: str
    created_at: datetime | None = None
    facts_count: int = 0
    preferences: str = ""
    invariants_count: int = 0


class DeleteProfileResult(_Base):
    """Результат удаления профиля задачи."""

    deleted: bool
    linked: bool = False


class TaskProfileDetail(_Base):
    """Профиль задачи с полной памятью (факты и инварианты)."""

    id: str
    name: str
    description: str
    created_at: datetime | None = None
    facts: list[str] = Field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = Field(default_factory=list)


class KnowledgeBase(_Base):
    """База знаний."""

    id: int
    name: str
    description: str | None = None
    embedding_model: str
    embedding_dimension: int
    created_at: datetime
    updated_at: datetime | None = None
    document_count: int | None = None
    chunk_count: int | None = None


class Document(_Base):
    """Документ базы знаний."""

    id: int
    knowledge_base_id: int
    name: str
    source_type: str
    source_path: str | None = None
    status: str
    error_message: str | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None


class Chunk(_Base):
    """Чанк документа."""

    id: int
    document_id: int
    chunk_index: int
    text: str
    char_start: int | None = None
    char_end: int | None = None
    token_count: int | None = None
    created_at: datetime


class RagContextChunk(_Base):
    """Чанк, найденный RAG-поиском."""

    chunk_id: int
    document_id: int
    knowledge_base_id: int
    document_name: str
    chunk_index: int
    text: str
    vector_distance: float | None = None
    rerank_score: float | None = None
    relevance: float | None = None


class MemorySaveResult(_Base):
    """Результат сохранения памяти чата."""

    chat_name: str
    success: bool
    duration_seconds: float
    error: str | None = None
    timed_out: bool = False


class GlobalMemory(_Base):
    """Глобальная память о пользователе."""

    facts: list[str] = Field(default_factory=list)


class DocumentUploadResult(_Base):
    """Итог добавления документов в базу знаний."""

    documents: list[Document] = Field(default_factory=list)
    ready_count: int = 0
    error_count: int = 0


# ---------------------------------------------------------------------------
# Входные тела запросов
# ---------------------------------------------------------------------------


class StrategySelectionInput(BaseModel):
    """Выбор стратегии управления контекстным окном (вход)."""

    strategy_type: str = "DefaultStrategy"
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    window_size: int | None = None


class CreateChatRequest(BaseModel):
    """Тело запроса создания чата."""

    name: str = ""
    system_prompt: str | None = None
    settings: Settings = Field(default_factory=Settings)
    strategy: StrategySelectionInput | None = None
    task_profile_id: str | None = None


class SendMessageRequest(BaseModel):
    """Тело запроса отправки сообщения."""

    message: str = Field(min_length=1)


class ChangePhaseRequest(BaseModel):
    """Тело запроса смены фазы."""

    command: str


class CommandRequest(BaseModel):
    """Тело запроса ассистентской команды."""

    command: str = Field(min_length=1)


class BranchRequest(BaseModel):
    """Тело запроса создания ветки."""

    name: str | None = None


class RerankRequest(BaseModel):
    """Тело запроса переключения реранкинга."""

    enabled: bool


class ConnectMcpRequest(BaseModel):
    """Тело запроса подключения MCP-сервера."""

    server_name: str


class CreateTaskProfileRequest(BaseModel):
    """Тело запроса создания профиля задачи."""

    name: str
    description: str
    preferences: str = ""
    invariants: list[str] | None = None


class AddInvariantRequest(BaseModel):
    """Тело запроса добавления инварианта."""

    text: str


class CreateKnowledgeBaseRequest(BaseModel):
    """Тело запроса создания базы знаний."""

    name: str
    description: str | None = None


class SearchRequest(BaseModel):
    """Тело запроса поиска по базе знаний."""

    query: str
    top_k: int | None = None


class SummaryResponse(BaseModel):
    """Ответ с саммари диалога."""

    summary: str | None = None


class RerankResult(BaseModel):
    """Результат переключения реранкинга."""

    enabled: bool
