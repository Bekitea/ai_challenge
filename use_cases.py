from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime

from chunking import chunk_text
from config import (
    DEFAULT_PROVIDER,
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_PROVIDER,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_FILE_EXTENSIONS,
    RAG_FILE_MAX_BYTES,
    RAG_FOLDER_MAX_FILES,
)
from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.rag_context_chunk import RagContextChunk
from core.domain.dtos.rag_retrieval_result import RagRetrievalResult
from core.domain.dtos.task_memory import TaskMemory
from core.domain.dtos.task_profile import TaskProfile
from core.domain.dtos.tool_call import ToolCall
from core.domain.entities.agent import Agent
from core.domain.entities.agent_phase import AgentPhase
from core.domain.entities.context_window_strategy import ContextWindowStrategy
from core.domain.entities.default_strategy import DefaultStrategy
from core.domain.entities.key_value_memory_strategy import KeyValueMemoryStrategy
from core.domain.entities.sliding_window_strategy import SlidingWindowStrategy
from core.domain.entities.summarization_strategy import SummarizationStrategy
from core.domain.exceptions.context_window_exceeded_error import (  # noqa: F401
    ContextWindowExceededError,
)
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.domain.protocols.agent_repository import AgentRepository
from core.domain.protocols.llm_provider import LlmProvider
from file_extractor import extract_from_path
from llm_providers import LlmProviderRegistry
from rag_errors import (
    DocumentIndexingError,
    EmbeddingDimensionMismatchError,
    KnowledgeBaseNotFoundError,
    RagError,  # noqa: F401 — реэкспорт базовой ошибки RAG для CLI
)
from rag_models import (
    DOCUMENT_STATUS_ERROR,
    ChunkDTO,
    DocumentDTO,
    KnowledgeBaseDTO,
)
from rag_service import RagModelService, RagService
from storage.api_key_repository import DatabaseApiKeyRepository
from storage.rag_repositories import (
    AgentKnowledgeBaseRepository,
    ChunkIngest,
    DocumentRepository,
    KnowledgeBaseRepository,
)


@dataclass
class UseCasesBundle:
    """Единый контейнер всех use cases для слоёв представления.

    Единственное определение в проекте: его импортирует и ``app_factory``
    (создаёт), и ``cli_app`` (потребляет), и будущий API-слой. Поля описаны
    forward-reference'ами, поэтому класс объявлен до классов use cases.
    """

    create_chat: CreateChatUseCase
    select_chat: SelectChatUseCase
    send_message: SendMessageUseCase
    view_settings: ViewSettingsUseCase
    change_settings: ChangeSettingsUseCase
    set_reranker_enabled: SetRerankerEnabledUseCase
    change_phase: ChangePhaseUseCase
    list_models: ListModelsUseCase
    show_history: ShowHistoryUseCase
    show_summary: ShowSummaryUseCase
    show_chat_info: ShowChatInfoUseCase
    create_branch: CreateBranchUseCase
    select_strategy: SelectContextStrategyUseCase
    view_global_memory: ViewGlobalMemoryUseCase
    refresh_agent_memory: RefreshAgentMemoryUseCase
    save_agent_memory: SaveAgentMemoryUseCase
    save_unsaved_memories: SaveUnsavedMemoriesUseCase
    list_task_profiles: ListTaskProfilesUseCase
    create_task_profile: CreateTaskProfileUseCase
    get_task_profile_memory: GetTaskProfileMemoryUseCase
    delete_task_profile: DeleteTaskProfileUseCase
    add_invariant: AddInvariantUseCase
    remove_invariant: RemoveInvariantUseCase
    list_invariants: ListInvariantsUseCase
    connect_mcp: ConnectMcpUseCase
    disconnect_mcp: DisconnectMcpUseCase
    list_connected_mcp: ListConnectedMcpUseCase
    list_available_mcp: ListAvailableMcpUseCase
    run_scheduled_agent_task: RunScheduledAgentTaskUseCase
    create_knowledge_base: CreateKnowledgeBaseUseCase
    delete_knowledge_base: DeleteKnowledgeBaseUseCase
    list_knowledge_bases: ListKnowledgeBasesUseCase
    add_document: AddDocumentToKnowledgeBaseUseCase
    list_documents: ListDocumentsUseCase
    list_document_chunks: ListDocumentChunksUseCase
    delete_document: DeleteDocumentUseCase
    attach_knowledge_base: AttachKnowledgeBaseToAgentUseCase
    detach_knowledge_base: DetachKnowledgeBaseFromAgentUseCase
    list_agent_knowledge_bases: ListAgentKnowledgeBasesUseCase
    retrieve_rag_context: RetrieveRagContextUseCase
    search_knowledge_base: SearchKnowledgeBaseUseCase
    create_api_key: CreateApiKeyUseCase
    list_api_keys: ListApiKeysUseCase
    delete_api_key: DeleteApiKeyUseCase
    verify_api_key: VerifyApiKeyUseCase


# ---------------------------------------------------------------------------
# DTO — единственный язык обмена между слоем представления и бизнес-логикой.
# Ни один бизнес-объект (Agent, Prompt, AgentSettings, …) не выходит наружу.
# ---------------------------------------------------------------------------


@dataclass
class ChatPreviewDTO:
    """Превью чата для списка чатов."""

    agent_id: int
    name: str
    last_message_timestamp: datetime | None
    message_count: int
    last_message_preview: str | None = None


@dataclass
class ChatDTO:
    """Идентификатор и базовые атрибуты чата (агенда)."""

    agent_id: int
    name: str
    strategy_type: str
    current_phase: str
    system_prompt: str | None = None
    task_profile_name: str | None = None


@dataclass
class TaskMemoryDTO:
    """DTO памяти задачи текущего диалога."""

    goal: str = ""
    constraints: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Возвращает True, если память не содержит данных."""
        return not (
            self.goal or self.constraints or self.terms or self.clarifications
        )


@dataclass
class ChatInfo:
    """Информация о чате для отображения (DTO)."""

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
    task_memory: TaskMemoryDTO | None = None


@dataclass
class SettingsDTO:
    """DTO настроек чата. Используется и на вход, и на выход."""

    model_id: str | None = None
    provider: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None
    reranker_enabled: bool = True


@dataclass
class HistoryMessageDTO:
    """Одно сообщение истории диалога (DTO)."""

    role: str
    content: str
    reasoning: str | None = None
    has_tool_calls: bool = False
    timestamp: datetime | None = None


@dataclass
class RagSourceDTO:
    """Источник RAG, использованный в ответе ассистента (DTO)."""

    document_name: str
    chunk_id: int
    chunk_index: int
    text: str
    relevance: float | None = None


@dataclass
class MessageResponseDTO:
    """Ответ ассистента на сообщение пользователя (DTO)."""

    content: str
    reasoning: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    context_window_size: int | None = None
    rag_sources: list[RagSourceDTO] | None = None


@dataclass
class AvailableMcpServerDTO:
    """MCP-сервер из реестра, доступный для подключения (DTO)."""

    name: str
    title: str
    description: str


@dataclass
class PhaseChangeResultDTO:
    """Результат команды перехода по фазам."""

    success: bool
    message: str
    current_phase: str


@dataclass
class DeleteProfileResultDTO:
    """Результат удаления профиля задачи."""

    deleted: bool
    linked: bool = False


def _settings_to_agent_settings(dto: SettingsDTO) -> AgentSettings:
    """Преобразует DTO настроек в бизнес-объект ``AgentSettings``."""
    return AgentSettings(
        model_id=dto.model_id,
        provider=dto.provider,
        top_k=dto.top_k,
        top_p=dto.top_p,
        temperature=dto.temperature,
        max_tokens=dto.max_tokens,
        reasoning_effort=dto.reasoning_effort,
        context_window_size=dto.context_window_size,
        reranker_enabled=dto.reranker_enabled,
    )


def _agent_settings_to_dto(settings: AgentSettings) -> SettingsDTO:
    """Преобразует ``AgentSettings`` в DTO настроек."""
    return SettingsDTO(
        model_id=settings.model_id,
        provider=settings.provider,
        top_k=settings.top_k,
        top_p=settings.top_p,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        reasoning_effort=settings.reasoning_effort,
        context_window_size=settings.context_window_size,
        reranker_enabled=settings.reranker_enabled,
    )


def _task_memory_to_dto(memory: TaskMemory) -> TaskMemoryDTO:
    """Преобразует бизнес-объект памяти задачи в DTO."""
    return TaskMemoryDTO(
        goal=memory.goal,
        constraints=list(memory.constraints),
        terms=list(memory.terms),
        clarifications=list(memory.clarifications),
    )


def _agent_to_chat_dto(agent: Agent) -> ChatDTO:
    """Преобразует ``Agent`` в ``ChatDTO`` (без утечки бизнес-объекта)."""
    system_prompt = None
    for message in agent.get_history():
        if message.role == "system":
            system_prompt = message.content
            break
    return ChatDTO(
        agent_id=agent.agent_id,
        name=agent.name,
        strategy_type=agent.strategy.strategy_type,
        current_phase=agent.current_phase.name,
        system_prompt=system_prompt,
        task_profile_name=(
            agent.task_profile.name if agent.task_profile is not None else None
        ),
    )


def _load_agent(repository: AgentRepository, agent_id: int | None) -> Agent | None:
    """Загружает агента по ``agent_id`` (None-safe)."""
    if agent_id is None:
        return None
    return repository.get_agent(agent_id)


def _task_profile_to_info(profile: TaskProfile) -> TaskProfileInfo:
    """Преобразует ``TaskProfile`` в краткий DTO для списка."""
    return TaskProfileInfo(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        created_at=profile.created_at,
        facts_count=len(profile.facts),
        preferences=profile.preferences or "",
        invariants_count=len(profile.invariants),
    )


def _task_profile_to_detail(profile: TaskProfile) -> TaskProfileDetailDTO:
    """Преобразует ``TaskProfile`` в детальный DTO с памятью."""
    return TaskProfileDetailDTO(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        created_at=profile.created_at,
        facts=list(profile.facts),
        preferences=profile.preferences or "",
        invariants=list(profile.invariants),
    )


def _require_agent(repository: AgentRepository, agent_id: int) -> Agent:
    """Загружает агента или бросает ValueError, если он не найден."""
    agent = repository.get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Чат #{agent_id} не найден")
    return agent


def _resolve_llm_provider(
    registry: LlmProviderRegistry, agent: Agent
) -> LlmProvider:
    """Возвращает провайдера, выбранного в настройках чата.

    Если провайдер не задан (старые чаты), используется ``DEFAULT_PROVIDER``.
    """
    provider_name = agent.get_settings().provider or DEFAULT_PROVIDER
    provider = registry.get(provider_name)
    if provider is None:
        available = ", ".join(registry.all()) or "нет"
        raise ValueError(
            f"Провайдер '{provider_name}' недоступен. "
            f"Доступные провайдеры: {available}."
        )
    return provider


def _retrieve_rag_context(
    rag_service: RagService | None, agent: Agent, query: str
) -> RagRetrievalResult:
    """Поднимает RAG-контекст, деградируя без него при ошибке провайдера."""
    if rag_service is None or agent.agent_id is None:
        return RagRetrievalResult(chunks=[], has_knowledge_bases=False)
    try:
        return rag_service.retrieve(
            agent.agent_id,
            query,
            reranker_enabled=agent.get_settings().reranker_enabled,
        )
    except Exception:
        logging.getLogger("agent.rag").debug(
            "RAG-поиск недоступен, диалог продолжен без контекста",
            exc_info=True,
        )
        return RagRetrievalResult(chunks=[], has_knowledge_bases=False)


def _collect_mcp_tools(agent: Agent) -> list[dict]:
    """Собирает OpenAI-описания инструментов живых MCP-подключений чата.

    Если сохранённый сервер ещё не имеет живого подключения в текущем
    процессе, выполняется попытка переподключения — иначе запрос к LLM ушёл
    бы без tools, и модель ответила бы «у меня нет доступа к инструменту».
    """
    from mcp_client import MCP_MANAGER

    logger = logging.getLogger("agent.mcp")

    if not agent.connected_mcp_servers or agent.agent_id is None:
        return []
    tools: list[dict] = []
    connections = MCP_MANAGER.get_connections(agent.agent_id)
    for server_name in agent.connected_mcp_servers:
        conn = connections.get(server_name)
        if conn is None or not conn.connected:
            conn, error = _reconnect_mcp(agent, server_name, MCP_MANAGER)
            if conn is None:
                logger.warning(
                    "MCP-сервер '%s' недоступен для чата #%s (%s): %s",
                    server_name,
                    agent.agent_id,
                    agent.name,
                    error or "неизвестная ошибка",
                )
                continue
        tools.extend(tool.to_openai_tool() for tool in conn.tools)
    return tools


def _reconnect_mcp(agent: Agent, server_name: str, manager):
    """Переподключает сохранённый MCP-сервер в текущем процессе."""
    from mcp_client import McpConnection
    from mcp_registry import find_server

    server_info = find_server(server_name)
    if server_info is None:
        return None, f"сервер '{server_name}' не найден в реестре"
    connection = McpConnection(server_info)
    connection.connect_and_list_tools()
    if not connection.connected:
        return None, connection.connect_error or "сервер не вернул инструменты"
    manager.add_connection(agent.agent_id, connection)
    return connection, None


class _McpToolExecutor:
    """Исполнитель tool-вызовов через живые MCP-подключения чата.

    Скрывает от домена инфраструктуру MCP: агент лишь просит исполнить
    ``ToolCall`` и не знает, откуда пришёл инструмент.
    """

    def __init__(self, agent: Agent):
        self._agent = agent

    def execute(self, call: ToolCall) -> str:
        from mcp_client import MCP_MANAGER, parse_tool_arguments, strip_prefix

        server_name, tool_name = strip_prefix(call.name)
        connections = (
            MCP_MANAGER.get_connections(self._agent.agent_id)
            if self._agent.agent_id is not None
            else {}
        )
        conn = connections.get(server_name)
        if conn is None or not conn.connected:
            return (
                f"[MCP] Ошибка: сервер '{server_name}' не подключен к чату, "
                f"инструмент '{tool_name}' недоступен."
            )
        arguments = parse_tool_arguments(call.arguments)
        return conn.call_tool(tool_name, arguments)


def _build_strategy(selection: StrategySelection) -> ContextWindowStrategy:
    """Создаёт стратегию управления контекстом из DTO-описания выбора."""
    if selection.strategy_type == "SummarizationStrategy":
        return SummarizationStrategy(
            non_compressible_count=selection.non_compressible_count or 2,
            buffer_size=selection.buffer_size or 3,
        )
    if selection.strategy_type == "KeyValueMemoryStrategy":
        return KeyValueMemoryStrategy(
            non_compressible_count=selection.non_compressible_count or 2,
            buffer_size=selection.buffer_size or 3,
        )
    if selection.strategy_type == "SlidingWindowStrategy":
        return SlidingWindowStrategy(window_size=selection.window_size or 10)
    return DefaultStrategy()


def _response_to_dto(response: LlmResponse, agent: Agent) -> MessageResponseDTO:
    """Преобразует ``LlmResponse`` + состояние агента в ``MessageResponseDTO``."""
    counters = agent.token_counters
    rag_sources = None
    if response.rag_sources is not None:
        rag_sources = [
            RagSourceDTO(
                document_name=chunk.document_name,
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                relevance=chunk.relevance,
            )
            for chunk in response.rag_sources
        ]
    return MessageResponseDTO(
        content=response.content,
        reasoning=response.reasoning,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_prompt_tokens=counters.total_prompt_tokens,
        total_completion_tokens=counters.total_completion_tokens,
        context_window_size=agent.get_settings().context_window_size,
        rag_sources=rag_sources,
    )


@dataclass
class StrategySelection:
    """Выбранная стратегия с параметрами."""

    strategy_type: str
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    window_size: int | None = None


@dataclass
class TaskProfileInfo:
    """Информация о профиле задачи для отображения."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts_count: int
    preferences: str = ""
    invariants_count: int = 0


@dataclass
class TaskProfileDetailDTO:
    """Профиль задачи с полной памятью (факты + инварианты)."""

    id: str
    name: str
    description: str
    created_at: datetime | None
    facts: list[str] = field(default_factory=list)
    preferences: str = ""
    invariants: list[str] = field(default_factory=list)


@dataclass
class InvariantInfo:
    """Информация об инварианте для отображения."""

    id: int
    text: str
    created_at: datetime


@dataclass
class AvailableModel:
    """Доступная для выбора модель с указанием провайдера.

    Одна и та же модель может предоставляться разными провайдерами, поэтому
    в списке для UI она представлена отдельной записью на каждого провайдера.
    """

    provider: str
    model_id: str
    display_name: str


class CreateChatUseCase:
    """Use case для создания нового чата."""

    def __init__(
        self,
        repository: AgentRepository,
        task_profile_repository=None,
    ):
        self.repository = repository
        self.task_profile_repository = task_profile_repository

    def execute(
        self,
        name: str,
        system_prompt: str | None,
        settings: SettingsDTO,
        strategy_selection: StrategySelection,
        task_profile_id: str | None = None,
        initial_phase: str | None = None,
    ) -> ChatDTO:
        """
        Создаёт новый чат с указанными настройками.

        Args:
            name: Название чата. Пустая строка — имя генерируется автоматически
                («Чат N» по текущему количеству чатов).
            system_prompt: Системный промпт (опционально).
            settings: Настройки агента (DTO).
            strategy_selection: Выбор стратегии управления контекстным окном.
            task_profile_id: UUID профиля задачи (опционально).
            initial_phase: Стартовая фаза агента (``plan``/``execute``/...).
                По умолчанию PLAN.

        Returns:
            ChatDTO: Созданный чат.

        Raises:
            ValueError: Если указан несуществующий профиль задачи.
        """
        # Проверка существования профиля задачи, если он указан
        if task_profile_id is not None and self.task_profile_repository is not None:
            profile = self.task_profile_repository.get_profile_by_id(task_profile_id)
            if profile is None:
                raise ValueError(f"Профиль задачи с ID {task_profile_id} не найден")

        if not name:
            name = f"Чат {len(self.repository.get_all_previews()) + 1}"

        agent = self.repository.create_agent(
            name=name,
            initial_settings=_settings_to_agent_settings(settings),
            system_prompt=system_prompt,
            strategy=_build_strategy(strategy_selection),
            task_profile_id=task_profile_id,
            initial_phase=AgentPhase(initial_phase) if initial_phase else None,
        )
        return _agent_to_chat_dto(agent)


class SelectChatUseCase:
    """Use case для выбора существующего чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def get_all_previews(self) -> list[ChatPreviewDTO]:
        """Получает список всех чатов (DTO)."""
        return [
            ChatPreviewDTO(
                agent_id=preview.agent_id,
                name=preview.name,
                last_message_timestamp=preview.last_message_timestamp,
                message_count=preview.message_count,
                last_message_preview=preview.last_message_preview,
            )
            for preview in self.repository.get_all_previews()
        ]

    def get_chat(self, agent_id: int) -> ChatDTO | None:
        """Получает чат (DTO) по числовому ID."""
        agent = self.repository.get_agent(agent_id)
        return _agent_to_chat_dto(agent) if agent is not None else None


class SendMessageUseCase:
    """Use case для отправки сообщения и получения ответа."""

    def __init__(
        self,
        repository: AgentRepository,
        registry: LlmProviderRegistry,
        rag_service: RagService | None = None,
    ):
        self.repository = repository
        self._registry = registry
        self._rag_service = rag_service

    def execute(
        self,
        agent_id: int,
        user_message: str,
        on_memory_warning: Callable[[str], None] | None = None,
    ) -> MessageResponseDTO:
        """
        Отправляет сообщение агенту и получает ответ.

        Args:
            agent_id: ID чата, которому адресовано сообщение.
            user_message: Текст сообщения пользователя.
            on_memory_warning: Необязательный колбэк для сообщений о сбое
                обновления памяти задачи диалога.

        Returns:
            MessageResponseDTO: Ответ ассистента и счётчики токенов.

        Raises:
            ContextWindowExceededError: Если превышен лимит контекстного окна.
        """
        agent = _require_agent(self.repository, agent_id)
        llm_provider = _resolve_llm_provider(self._registry, agent)
        rag_result = _retrieve_rag_context(self._rag_service, agent, user_message)
        tools = _collect_mcp_tools(agent)
        tool_executor = _McpToolExecutor(agent) if tools else None
        response = agent.continue_dialog(
            user_message,
            repository=self.repository,
            llm_provider=llm_provider,
            rag_result=rag_result,
            tools=tools or None,
            tool_executor=tool_executor,
            on_memory_warning=on_memory_warning,
        )
        return _response_to_dto(response, agent)


class ViewSettingsUseCase:
    """Use case для просмотра настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> SettingsDTO | None:
        """Получает настройки чата (DTO)."""
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        return _agent_settings_to_dto(agent.get_settings())


class ChangeSettingsUseCase:
    """Use case для изменения настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, new_settings: SettingsDTO) -> None:
        """
        Обновляет настройки чата.

        Args:
            agent_id: ID чата для обновления.
            new_settings: Новые настройки (DTO).
        """
        agent = _require_agent(self.repository, agent_id)
        agent.update_settings(
            _settings_to_agent_settings(new_settings), self.repository
        )


class SetRerankerEnabledUseCase:
    """Use case включения/отключения реранкинга для конкретного чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, enabled: bool) -> bool:
        """Обновляет per-chat флаг реранкинга, сохраняя остальные настройки."""
        agent = _require_agent(self.repository, agent_id)
        current = agent.get_settings()
        agent.update_settings(
            replace(current, reranker_enabled=bool(enabled)), self.repository
        )
        return bool(enabled)


class ListModelsUseCase:
    """Use case получения списка доступных моделей всех провайдеров.

    Опрашивает провайдеров динамически (Yandex Cloud и Ollama), поэтому
    хардкода моделей в приложении больше нет. Недоступный провайдер просто
    не попадает в результат.
    """

    def __init__(self, registry: LlmProviderRegistry):
        self._registry = registry

    def execute(self) -> list[AvailableModel]:
        """Возвращает список доступных моделей с указанием провайдера."""
        return [
            AvailableModel(
                provider=provider_name,
                model_id=info.model_id,
                display_name=info.display_name,
            )
            for provider_name, info in self._registry.list_models()
        ]


class ShowHistoryUseCase:
    """Use case для показа истории чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> list[HistoryMessageDTO] | None:
        """Получает историю сообщений чата (DTO)."""
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        return [
            HistoryMessageDTO(
                role=message.role,
                content=message.content,
                reasoning=message.reasoning,
                has_tool_calls=bool(message.tool_calls),
                timestamp=message.timestamp,
            )
            for message in agent.get_history()
        ]


class ShowSummaryUseCase:
    """Use case для показа саммари диалога."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> str | None:
        """
        Получает саммари из стратегии чата.

        Args:
            agent_id: ID чата.

        Returns:
            Саммари или None, если оно отсутствует.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None

        strategy = agent.strategy
        if hasattr(strategy, "summary"):
            return strategy.summary
        return None


class ShowChatInfoUseCase:
    """Use case для показа информации о чате."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> ChatInfo | None:
        """
        Получает информацию о чате включая счетчики токенов (DTO).

        Args:
            agent_id: ID чата.

        Returns:
            ChatInfo или None, если чат не найден.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is None:
            return None
        agent.refresh_memory(self.repository)

        counters = agent.token_counters
        strategy = agent.strategy

        has_summary = False
        non_compressible_count = None
        buffer_size = None
        task_profile_name = None

        if hasattr(strategy, "summary") and strategy.summary:
            has_summary = True
        if hasattr(strategy, "non_compressible_count"):
            non_compressible_count = strategy.non_compressible_count
        if hasattr(strategy, "buffer_size"):
            buffer_size = strategy.buffer_size
        if agent.task_profile is not None:
            task_profile_name = agent.task_profile.name

        current_phase = agent.current_phase.value if agent.current_phase else None

        return ChatInfo(
            name=agent.name,
            agent_id=agent.agent_id,
            strategy_type=strategy.strategy_type,
            message_count=agent.message_count,
            total_prompt_tokens=counters.total_prompt_tokens,
            total_completion_tokens=counters.total_completion_tokens,
            has_summary=has_summary,
            non_compressible_count=non_compressible_count,
            buffer_size=buffer_size,
            task_profile_name=task_profile_name,
            current_phase=current_phase,
            task_memory=_task_memory_to_dto(agent.task_memory),
        )


class CreateBranchUseCase:
    """Use case для создания ветки текущего чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, new_name: str | None = None) -> ChatDTO:
        """
        Создаёт ветку текущего чата.

        Args:
            agent_id: ID родительского чата.
            new_name: Новое название для ветки (опционально).

        Returns:
            ChatDTO: Новая ветка.
        """
        parent_agent = _require_agent(self.repository, agent_id)
        branch = parent_agent.branch(
            new_name=new_name, repository=self.repository
        )

        # Переносим живые MCP-подключения на ветку (регистрация под новым ID)
        if parent_agent.agent_id is not None and branch.agent_id is not None:
            from mcp_client import MCP_MANAGER

            connections = MCP_MANAGER.get_connections(parent_agent.agent_id)
            for server_name in branch.connected_mcp_servers:
                conn = connections.get(server_name)
                if conn is not None:
                    MCP_MANAGER.add_connection(branch.agent_id, conn)

        return _agent_to_chat_dto(branch)


class ChangePhaseUseCase:
    """Use case перехода агента между фазами (PLAN/EXECUTE/VALIDATE/REPORT)."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, command: str) -> PhaseChangeResultDTO:
        """Обрабатывает команду перехода по фазам (``/plan``, ``/execute``, …)."""
        agent = _require_agent(self.repository, agent_id)
        success, message = agent.handle_phase_command(command, self.repository)
        return PhaseChangeResultDTO(
            success=success,
            message=message,
            current_phase=agent.current_phase.name,
        )


class SelectContextStrategyUseCase:
    """Use case для выбора стратегии управления контекстным окном."""

    def execute(self, selection: StrategySelection) -> ContextWindowStrategy:
        """
        Создаёт стратегию на основе выбора пользователя.

        Args:
            selection: Выбранная стратегия с параметрами.

        Returns:
            ContextWindowStrategy: Экземпляр стратегии.
        """
        return _build_strategy(selection)


class ViewGlobalMemoryUseCase:
    """Use case для просмотра глобальной памяти агента."""

    def __init__(self, memory_repository):
        self.memory_repository = memory_repository

    def execute(self) -> list[str]:
        """
        Получает список фактов из глобальной памяти.

        Returns:
            Список фактов.
        """
        memory = self.memory_repository.get_memory()
        return memory.facts


class RefreshAgentMemoryUseCase:
    """Use case для загрузки памяти агента при выборе чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int) -> None:
        """
        Загружает общесистемную память и память задачи для чата.

        Args:
            agent_id: ID чата, для которого нужно загрузить память.
        """
        agent = _load_agent(self.repository, agent_id)
        if agent is not None:
            agent.refresh_memory(self.repository)


@dataclass
class MemorySaveResult:
    """Результат заполнения долговременной памяти одного чата.

    Attributes:
        chat_name: Имя чата, для которого сохранялась память.
        success: Успешно ли выполнено сохранение.
        duration_seconds: Сколько времени заняло заполнение памяти.
        error: Текст ошибки при неудаче (иначе None).
        timed_out: True, если ошибка вызвана таймаутом запроса к модели.
    """

    chat_name: str
    success: bool
    duration_seconds: float
    error: str | None = None
    timed_out: bool = False


def _save_agent_memory(
    agent: Agent,
    repository: AgentRepository,
    registry: LlmProviderRegistry,
    on_warning: Callable[[str], None] | None = None,
) -> MemorySaveResult:
    """Заполняет глобальную и профильную память агента с замером времени."""
    start = time.perf_counter()
    try:
        llm_provider = _resolve_llm_provider(registry, agent)
        agent.save_memory(
            repository=repository,
            llm_provider=llm_provider,
            on_warning=on_warning,
        )
    except Exception as e:  # noqa: BLE001
        return MemorySaveResult(
            chat_name=agent.name,
            success=False,
            duration_seconds=time.perf_counter() - start,
            error=str(e),
            timed_out=isinstance(e, LlmTimeoutError),
        )
    return MemorySaveResult(
        chat_name=agent.name,
        success=True,
        duration_seconds=time.perf_counter() - start,
    )


class SaveAgentMemoryUseCase:
    """Use case для сохранения памяти агента при выходе из чата."""

    def __init__(
        self, repository: AgentRepository, registry: LlmProviderRegistry
    ):
        self.repository = repository
        self._registry = registry

    def execute(
        self,
        agent_id: int,
        on_warning: Callable[[str], None] | None = None,
    ) -> MemorySaveResult:
        """
        Сохраняет общесистемную память о пользователе и память профиля задачи.

        Args:
            agent_id: ID чата, для которого нужно сохранить память.
            on_warning: Необязательный колбэк для сообщений о сбое памяти задачи.

        Returns:
            Результат заполнения памяти чата (успех, длительность, ошибка).
        """
        agent = _require_agent(self.repository, agent_id)
        return _save_agent_memory(
            agent, self.repository, self._registry, on_warning=on_warning
        )


class SaveUnsavedMemoriesUseCase:
    """Use case для сохранения всех несохранённых памятей при старте приложения."""

    def __init__(
        self, repository: AgentRepository, registry: LlmProviderRegistry
    ):
        self.repository = repository
        self._registry = registry

    def execute(
        self,
        on_agent_start: Callable[[str], None] | None = None,
        on_result: Callable[[MemorySaveResult], None] | None = None,
        on_warning: Callable[[str], None] | None = None,
    ) -> list[MemorySaveResult]:
        """
        Находит все агенты с несохранёнными промптами и сохраняет их память.

        Агент считается имеющим несохранённые промпты, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False

        Если сохранение одного чата падает по таймауту модели, обработка серии
        прерывается (circuit breaker), оставшиеся чаты пропускаются с
        предупреждением через ``on_warning``.

        Args:
            on_agent_start: Необязательный колбэк(chat_name), вызывается перед
                сохранением памяти каждого чата.
            on_result: Необязательный колбэк(MemorySaveResult), вызывается
                сразу после сохранения памяти каждого чата.
            on_warning: Необязательный колбэк(сообщение) для сбоев памяти задачи.

        Returns:
            Список результатов по каждому чату (успех, длительность, ошибка).
        """
        agents = self.repository.get_agents_with_unsaved_memory()

        results: list[MemorySaveResult] = []
        for index, agent in enumerate(agents):
            if on_agent_start is not None:
                on_agent_start(agent.name)
            result = _save_agent_memory(
                agent, self.repository, self._registry, on_warning=on_warning
            )
            results.append(result)
            if on_result is not None:
                on_result(result)
            if result.timed_out:
                skipped = len(agents) - index - 1
                if on_warning is not None and skipped:
                    on_warning(
                        "Сохранение памяти прервано из-за таймаута модели; "
                        f"пропущено чатов: {skipped}."
                    )
                break
        return results


class ListTaskProfilesUseCase:
    """Use case для просмотра списка профилей задач."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self) -> list[TaskProfileInfo]:
        """
        Получает список всех профилей задач.

        Returns:
            Список TaskProfileInfo.
        """
        profiles = self.task_profile_repository.get_all_profiles()
        return [_task_profile_to_info(p) for p in profiles]


class CreateTaskProfileUseCase:
    """Use case для создания нового профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(
        self,
        name: str,
        description: str,
        preferences: str = "",
        invariants: list[str] | None = None,
    ) -> TaskProfileInfo:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.
            preferences: Инструкции и предпочтения пользователя (опционально).
            invariants: Список строгих правил/ограничений (опционально).

        Returns:
            TaskProfileInfo: Созданный профиль.
        """
        profile = self.task_profile_repository.create_profile(
            name, description, preferences, invariants
        )
        return _task_profile_to_info(profile)


class GetTaskProfileMemoryUseCase:
    """Use case для просмотра памяти выбранного профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> TaskProfileDetailDTO | None:
        """
        Получает информацию о профиле задачи и его память.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            TaskProfileDetailDTO или None, если профиль не найден.
        """
        profile = self.task_profile_repository.get_profile_by_id(profile_id)
        if profile is None:
            return None
        return _task_profile_to_detail(profile)


class DeleteTaskProfileUseCase:
    """Use case для удаления профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def is_linked(self, profile_id: str) -> bool:
        """Возвращает True, если профиль привязан к агентам."""
        return self.task_profile_repository.is_profile_linked_to_agents(profile_id)

    def execute(self, profile_id: str) -> DeleteProfileResultDTO:
        """
        Удаляет профиль задачи.

        Args:
            profile_id: UUID профиля для удаления.

        Returns:
            DeleteProfileResultDTO: ``deleted`` — удалён ли профиль,
            ``linked`` — был ли отказ из-за привязки к агентам.
        """
        # Проверяем, привязан ли профиль к агентам
        if self.task_profile_repository.is_profile_linked_to_agents(profile_id):
            return DeleteProfileResultDTO(deleted=False, linked=True)

        return DeleteProfileResultDTO(
            deleted=self.task_profile_repository.delete_profile(profile_id)
        )


class AddInvariantUseCase:
    """Use case для добавления инварианта в профиль задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str, text: str) -> InvariantInfo:
        """
        Добавляет инвариант в профиль задачи.

        Args:
            profile_id: UUID профиля задачи.
            text: Текст инварианта (строгое правило/ограничение).

        Returns:
            InvariantInfo: Информация о созданном инварианте.

        Raises:
            ValueError: Если текст пустой или профиль не найден.
        """
        stripped = text.strip()
        if not stripped:
            raise ValueError("Текст инварианта не может быть пустым")
        invariant_id = self.task_profile_repository.add_invariant(profile_id, stripped)
        # Загружаем созданный инвариант для возврата полной информации
        invariants = self.task_profile_repository.get_invariants(profile_id)
        for inv in invariants:
            if inv["id"] == invariant_id:
                return InvariantInfo(
                    id=inv["id"],
                    text=inv["text"],
                    created_at=inv["created_at"],
                )
        raise RuntimeError("Инвариант не найден после создания")


class RemoveInvariantUseCase:
    """Use case для удаления инварианта из профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, invariant_id: int) -> bool:
        """
        Удаляет инвариант по ID.

        Args:
            invariant_id: ID инварианта для удаления.

        Returns:
            True, если инвариант был удалён, False если не найден.
        """
        return self.task_profile_repository.remove_invariant(invariant_id)


class ListInvariantsUseCase:
    """Use case для получения списка инвариантов профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> list[InvariantInfo]:
        """
        Возвращает список инвариантов профиля.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            Список InvariantInfo, отсортированный по дате создания.
        """
        invariants = self.task_profile_repository.get_invariants(profile_id)
        return [
            InvariantInfo(
                id=inv["id"],
                text=inv["text"],
                created_at=inv["created_at"],
            )
            for inv in invariants
        ]


# ---------------------------------------------------------------------------
# Use cases для работы с MCP-серверами
# ---------------------------------------------------------------------------


@dataclass
class McpServerStatus:
    """Статус MCP-сервера в контексте чата."""

    name: str  # машинное имя сервера
    title: str  # отображаемое название
    description: str  # описание для пользователя
    connected: bool  # есть ли живое подключение к этому чату
    tools: list[str]  # имена инструментов, доступных через это подключение


class ListConnectedMcpUseCase:
    """Use case для получения списка MCP-серверов, подключённых к чату."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> list[McpServerStatus]:
        """Возвращает статусы всех подключённых к чату MCP-серверов.

        В список попадают и серверы, сохранённые в чате, но недоступные в
        данный момент (живое подключение не установлено или разорвано) —
        они отображаются с connected=False.
        """
        from mcp_client import MCP_MANAGER
        from mcp_registry import find_server

        agent = _load_agent(self.repository, agent_id)
        if agent is None or agent.agent_id is None:
            return []

        connections = MCP_MANAGER.get_connections(agent.agent_id)
        result: list[McpServerStatus] = []
        for server_name in agent.connected_mcp_servers:
            info = find_server(server_name)
            conn = connections.get(server_name)
            live = conn is not None and conn.connected
            result.append(
                McpServerStatus(
                    name=server_name,
                    title=info.title if info else server_name,
                    description=info.description
                    if info
                    else "сервер отсутствует в реестре",
                    connected=live,
                    tools=[tool.name for tool in conn.tools] if live else [],
                )
            )
        return result


class ListAvailableMcpUseCase:
    """Use case для получения списка MCP-серверов, ещё не подключённых к чату."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int | None) -> list[AvailableMcpServerDTO]:
        """Возвращает не подключённые к чату MCP-серверы реестра (DTO)."""
        from mcp_registry import get_available_servers

        agent = _load_agent(self.repository, agent_id)
        connected = set(agent.connected_mcp_servers) if agent is not None else set()
        return [
            AvailableMcpServerDTO(
                name=server.name,
                title=server.title,
                description=server.description,
            )
            for server in get_available_servers()
            if server.name not in connected
        ]


class ConnectMcpUseCase:
    """Use case для подключения MCP-сервера к чату."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, server_name: str) -> tuple[bool, str]:
        """Подключает MCP-сервер к чату: соединение + сохранение списка серверов."""
        from mcp_client import MCP_MANAGER, McpConnection
        from mcp_registry import find_server

        agent = _require_agent(self.repository, agent_id)

        if agent.agent_id is None:
            return False, "Агент ещё не сохранён — подключите MCP позже."

        server_info = find_server(server_name)
        if server_info is None:
            return False, f"MCP-сервер '{server_name}' не найден в реестре."

        if server_name in agent.connected_mcp_servers:
            return False, f"MCP '{server_info.title}' уже подключен к этому чату."

        connection = McpConnection(server_info)
        tools = connection.connect_and_list_tools()
        if not connection.connected:
            return (
                False,
                (
                    f"Не удалось подключиться к MCP '{server_info.title}': "
                    f"{connection.connect_error or 'сервер не вернул инструменты'}"
                ),
            )

        MCP_MANAGER.add_connection(agent.agent_id, connection)
        agent.attach_mcp_server(server_name, self.repository)
        tool_names = ", ".join(t.name for t in tools) if tools else "нет"
        return (
            True,
            f"MCP '{server_info.title}' подключен. Доступные инструменты: {tool_names}",
        )


class DisconnectMcpUseCase:
    """Use case для отключения MCP-сервера от чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent_id: int, server_name: str) -> tuple[bool, str]:
        """Отключает MCP-сервер от чата."""
        from mcp_client import MCP_MANAGER
        from mcp_registry import find_server

        agent = _require_agent(self.repository, agent_id)

        if server_name not in agent.connected_mcp_servers:
            return False, f"MCP '{server_name}' не подключен к этому чату."

        server_info = find_server(server_name)
        title = server_info.title if server_info else server_name

        if agent.agent_id is not None:
            MCP_MANAGER.remove_connection(agent.agent_id, server_name)
        agent.detach_mcp_server(server_name, self.repository)
        return True, f"MCP '{title}' отключен."


@dataclass
class ScheduledReport:
    """Результат одного запуска периодической агентной задачи.

    Слой представления (Celery) получает только этот DTO — ни репозиториев,
    ни LLM-провайдера, ни внутренностей агента он не видит.
    """

    chat_name: str
    agent_id: int | None
    task: str  # запрос, отправленный агенту
    answer: str  # итоговый ответ агента (сводка)
    prompt_tokens: int
    completion_tokens: int


class RunScheduledAgentTaskUseCase:
    """Use case для выполнения периодической задачи агентом в новом чате.

    Инкапсулирует всю бизнес-логику сценария «отчёт по расписанию»:
    каждый запуск создаёт НОВЫЙ чат (переиспользование старого недопустимо:
    накопленная история контекста ломает периодические запросы), подключает
    в него необходимые MCP-серверы и отправляет агенту задание.

    Все зависимости передаются через конструктор фабрикой приложения
    (app_factory), поэтому Celery-слой общается с системой исключительно
    на языке use cases.
    """

    def __init__(
        self,
        create_chat: CreateChatUseCase,
        send_message: SendMessageUseCase,
        connect_mcp: ConnectMcpUseCase,
    ):
        self.create_chat = create_chat
        self.send_message = send_message
        self.connect_mcp = connect_mcp

    @staticmethod
    def _run_chat_name(base_name: str) -> str:
        """Формирует уникальное имя чата для конкретного запуска."""
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        return f"{base_name} · {stamp}"

    def execute(
        self,
        chat_name: str,
        system_prompt: str,
        task: str,
        mcp_servers: list[str] | None = None,
    ) -> ScheduledReport:
        """Выполняет задание task в специально созданном для него чате.

        Args:
            chat_name: Базовое имя отчёта; реальный чат получает уникальное
                имя на основе этого базового (отдельный чат на каждый запуск).
            system_prompt: Системный промпт для создаваемого чата.
            task: Запрос/задание, отправляемое агенту.
            mcp_servers: MCP-серверы, которые подключаются к новому чату
                перед отправкой задания.

        Returns:
            ScheduledReport: DTO с ответом агента и счётчиками токенов.
        """
        # Каждый запуск — новый чат с чистым контекстом. Ранее чат-резидент
        # переиспользовался между запусками: история накапливалась, а
        # MCP-подключения жили только в памяти процесса воркера и после
        # перезапуска «протухали» (имя осталось в БД, соединения нет), из-за
        # чего периодические запросы отрабатывали некорректно.
        #
        # Стартовая фаза — EXECUTE, а не PLAN: периодический отчёт полностью
        # неинтерактивен (никто не подтвердит переход фаз), а описание фазы
        # PLAN («обсуждай задачу, меняй фазу только по согласию пользователя»)
        # подставляется в системный промпт и заставляло модель вместо реального
        # вызова инструмента отвечать «подтвердите переход к выполнению» либо
        # печатать вызов функции текстом.
        agent = self.create_chat.execute(
            name=self._run_chat_name(chat_name),
            system_prompt=system_prompt,
            settings=SettingsDTO(
                provider=DEFAULT_REPORT_PROVIDER,
                model_id=DEFAULT_REPORT_MODEL,
            ),
            strategy_selection=StrategySelection(strategy_type="DefaultStrategy"),
            initial_phase="execute",
        )

        # Подключаем MCP-серверы к freshly created чату: живые соединения
        # создаются в этом же процессе воркера, поэтому гарантированно
        # доступны агенту при вызове LLM с tools.
        for server_name in mcp_servers or []:
            success, message = self.connect_mcp.execute(agent.agent_id, server_name)
            if not success:
                raise RuntimeError(
                    f"Не удалось подключить MCP-сервер '{server_name}' "
                    f"для периодического отчёта '{chat_name}': {message}"
                )

        response = self.send_message.execute(agent.agent_id, task)

        return ScheduledReport(
            chat_name=agent.name,
            agent_id=agent.agent_id,
            task=task,
            answer=response.content,
            prompt_tokens=response.total_prompt_tokens,
            completion_tokens=response.total_completion_tokens,
        )


# ---------------------------------------------------------------------------
# Use cases для работы с базами знаний (RAG)
# ---------------------------------------------------------------------------


@dataclass
class AddDocumentsResult:
    """Итог добавления документов в базу знаний."""

    documents: list[DocumentDTO]

    @property
    def ready_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status != DOCUMENT_STATUS_ERROR)

    @property
    def error_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status == DOCUMENT_STATUS_ERROR)


class CreateKnowledgeBaseUseCase:
    """Use case создания базы знаний."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        rag_model_service: RagModelService,
    ):
        self._kb_repository = knowledge_base_repository
        self._model_service = rag_model_service

    def execute(self, name: str, description: str | None = None) -> KnowledgeBaseDTO:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Название базы знаний не может быть пустым")

        return self._kb_repository.create(
            name=clean_name,
            description=(description or "").strip() or None,
            embedding_model=self._model_service.embedding_model_name,
            embedding_dimension=self._model_service.embedding_dimension,
        )


class DeleteKnowledgeBaseUseCase:
    """Use case удаления базы знаний."""

    def __init__(self, knowledge_base_repository: KnowledgeBaseRepository):
        self._kb_repository = knowledge_base_repository

    def execute(self, knowledge_base_id: int) -> bool:
        return self._kb_repository.delete(knowledge_base_id)


class ListKnowledgeBasesUseCase:
    """Use case получения списка баз знаний."""

    def __init__(self, knowledge_base_repository: KnowledgeBaseRepository):
        self._kb_repository = knowledge_base_repository

    def execute(self) -> list[KnowledgeBaseDTO]:
        return self._kb_repository.list()


class AddDocumentToKnowledgeBaseUseCase:
    """Use case добавления документа(ов) в базу знаний с индексацией.

    Источником может быть отдельный файл (.txt/.md/.py) или папка. Каждый файл
    становится отдельным документом. Индексация синхронная: при ошибке
    документ помечается статусом ``error`` и не участвует в поиске.
    """

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        rag_model_service: RagModelService,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
        file_extensions: set[str] | None = None,
        max_bytes: int = RAG_FILE_MAX_BYTES,
        max_files: int = RAG_FOLDER_MAX_FILES,
    ):
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository
        self._model_service = rag_model_service
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._file_extensions = file_extensions or set(RAG_FILE_EXTENSIONS)
        self._max_bytes = max_bytes
        self._max_files = max_files

    def execute(
        self, knowledge_base_id: int, source_path: str
    ) -> AddDocumentsResult:
        kb = self._kb_repository.get(knowledge_base_id)
        if kb is None:
            raise KnowledgeBaseNotFoundError(
                f"База знаний #{knowledge_base_id} не найдена."
            )

        if (
            kb.embedding_model != self._model_service.embedding_model_name
            or kb.embedding_dimension != self._model_service.embedding_dimension
        ):
            raise EmbeddingDimensionMismatchError(
                "Модель эмбеддинга текущего приложения не совпадает с моделью, "
                f"под которую создана база знаний '{kb.name}'."
            )

        extracted_files = extract_from_path(
            source_path,
            extensions=self._file_extensions,
            max_bytes=self._max_bytes,
            max_files=self._max_files,
        )

        documents: list[DocumentDTO] = []
        for extracted in extracted_files:
            document_id = self._document_repository.create_pending(
                kb_id=kb.id,
                name=extracted.name,
                source_type="file",
                source_path=extracted.source_path,
                content_hash=extracted.content_hash,
            )
            try:
                text_chunks = chunk_text(
                    extracted.text,
                    chunk_size=self._chunk_size,
                    overlap=self._chunk_overlap,
                )
                if not text_chunks:
                    raise DocumentIndexingError("Документ не содержит текста.")

                embeddings = self._model_service.embed_documents(
                    [chunk.text for chunk in text_chunks]
                )
                ingests = [
                    ChunkIngest(
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        token_count=chunk.token_count,
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(
                        text_chunks, embeddings, strict=True
                    )
                ]
                self._document_repository.store_indexed(
                    kb_id=kb.id,
                    document_id=document_id,
                    chunks=ingests,
                )
            except Exception as exc:  # noqa: BLE001
                self._document_repository.set_status(
                    document_id,
                    DOCUMENT_STATUS_ERROR,
                    error_message=str(exc),
                    chunk_count=0,
                )

            document = self._document_repository.get(document_id)
            if document is not None:
                documents.append(document)

        return AddDocumentsResult(documents=documents)


class ListDocumentsUseCase:
    """Use case получения списка документов базы знаний."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository

    def execute(self, knowledge_base_id: int) -> list[DocumentDTO]:
        if self._kb_repository.get(knowledge_base_id) is None:
            raise KnowledgeBaseNotFoundError(
                f"База знаний #{knowledge_base_id} не найдена."
            )
        return self._document_repository.list_by_kb(knowledge_base_id)


class ListDocumentChunksUseCase:
    """Use case получения чанков документа."""

    def __init__(self, document_repository: DocumentRepository):
        self._document_repository = document_repository

    def execute(self, document_id: int) -> list[ChunkDTO]:
        return self._document_repository.list_chunks(document_id)


class DeleteDocumentUseCase:
    """Use case удаления документа вместе с чанками и векторами."""

    def __init__(self, document_repository: DocumentRepository):
        self._document_repository = document_repository

    def execute(self, document_id: int) -> bool:
        return self._document_repository.delete(document_id)


class AttachKnowledgeBaseToAgentUseCase:
    """Use case подключения базы знаний к чату (агенту)."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        agent_knowledge_base_repository: AgentKnowledgeBaseRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int, knowledge_base_id: int) -> tuple[bool, str]:
        kb = self._kb_repository.get(knowledge_base_id)
        if kb is None:
            return False, f"База знаний #{knowledge_base_id} не найдена."

        created = self._agent_kb_repository.attach(agent_id, knowledge_base_id)
        if created:
            return True, f"База знаний '{kb.name}' подключена к чату."
        return True, f"База знаний '{kb.name}' уже подключена к чату."


class DetachKnowledgeBaseFromAgentUseCase:
    """Use case отключения базы знаний от чата (агента)."""

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        agent_knowledge_base_repository: AgentKnowledgeBaseRepository,
    ):
        self._kb_repository = knowledge_base_repository
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int, knowledge_base_id: int) -> tuple[bool, str]:
        kb = self._kb_repository.get(knowledge_base_id)
        name = kb.name if kb is not None else f"#{knowledge_base_id}"

        removed = self._agent_kb_repository.detach(agent_id, knowledge_base_id)
        if removed:
            return True, f"База знаний '{name}' отключена от чата."
        return True, f"База знаний '{name}' не была подключена к чату."


class ListAgentKnowledgeBasesUseCase:
    """Use case получения баз знаний, подключённых к чату."""

    def __init__(self, agent_knowledge_base_repository: AgentKnowledgeBaseRepository):
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent_id: int) -> list[KnowledgeBaseDTO]:
        return self._agent_kb_repository.list_for_agent(agent_id)


class RetrieveRagContextUseCase:
    """Use case поиска релевантных чанков по базам знаний агента.

    Используется CLI для проверки поиска; диалог агента обращается к
    ``RagService`` напрямую.
    """

    def __init__(self, rag_service: RagService):
        self._rag_service = rag_service

    def execute(
        self,
        agent_id: int | None,
        query_text: str,
        max_candidates: int | None = None,
        final_top_k: int | None = None,
        reranker_enabled: bool | None = None,
    ) -> list[RagContextChunk]:
        return self._rag_service.retrieve(
            agent_id=agent_id,
            query_text=query_text,
            max_candidates=max_candidates,
            final_top_k=final_top_k,
            reranker_enabled=reranker_enabled,
        ).chunks


class SearchKnowledgeBaseUseCase:
    """Use case поиска по одной базе знаний (для меню управления)."""

    def __init__(self, rag_service: RagService):
        self._rag_service = rag_service

    def execute(
        self, knowledge_base_id: int, query_text: str, top_k: int | None = None
    ) -> list[RagContextChunk]:
        return self._rag_service.search_knowledge_base(
            knowledge_base_id, query_text, top_k
        )


# ---------------------------------------------------------------------------
# API-ключи доступа к REST API.
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "aic_"


def _hash_api_key(api_key: str) -> str:
    """Возвращает SHA-256-хеш секрета API-ключа в hex-виде."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


@dataclass
class ApiKeyCreatedDTO:
    """Результат создания API-ключа.

    ``api_key`` содержит исходный секрет и возвращается вызывающему коду
    ровно один раз — при создании; сохранить его нужно сразу.
    """

    id: int
    name: str
    api_key: str
    created_at: datetime


@dataclass
class ApiKeyDTO:
    """Метаданные API-ключа без секрета."""

    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None


@dataclass
class DeleteApiKeyResultDTO:
    """Результат удаления API-ключа."""

    deleted: bool
    name: str | None


class CreateApiKeyUseCase:
    """Use case создания нового API-ключа."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, name: str) -> ApiKeyCreatedDTO:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Название API-ключа не может быть пустым.")

        api_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
        record = self._api_key_repository.create(
            name=clean_name,
            key_hash=_hash_api_key(api_key),
            prefix=api_key[: len(API_KEY_PREFIX) + 8],
        )
        return ApiKeyCreatedDTO(
            id=record.id,
            name=record.name,
            api_key=api_key,
            created_at=record.created_at,
        )


class ListApiKeysUseCase:
    """Use case получения списка API-ключей (без секретов)."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self) -> list[ApiKeyDTO]:
        return [
            ApiKeyDTO(
                id=record.id,
                name=record.name,
                prefix=record.prefix,
                created_at=record.created_at,
                last_used_at=record.last_used_at,
            )
            for record in self._api_key_repository.list_all()
        ]


class DeleteApiKeyUseCase:
    """Use case отзыва API-ключа по идентификатору."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, key_id: int) -> DeleteApiKeyResultDTO:
        record = self._api_key_repository.delete(key_id)
        if record is None:
            raise ValueError(f"API-ключ #{key_id} не найден.")
        return DeleteApiKeyResultDTO(deleted=True, name=record.name)


class VerifyApiKeyUseCase:
    """Use case проверки API-ключа при обращении к REST API."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, api_key: str) -> bool:
        if not api_key:
            return False
        record = self._api_key_repository.find_by_hash(_hash_api_key(api_key))
        if record is None:
            return False
        self._api_key_repository.touch(record.id)
        return True
