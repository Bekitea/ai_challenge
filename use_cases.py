from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from agents import (
    Agent,
    AgentPhase,
    AgentPreview,
    AgentSettings,
    Prompt,
    TaskMemory,
    TaskProfile,
)
from chunking import chunk_text
from config import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_FILE_EXTENSIONS,
    RAG_FILE_MAX_BYTES,
    RAG_FOLDER_MAX_FILES,
)
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    KeyValueMemoryStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
)
from file_extractor import extract_from_path
from llm_providers import LlmProvider, LlmResponse
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
    RagContextChunk,
)
from rag_service import RagModelService, RagService
from storage.agent_repositories import AgentRepository
from storage.rag_repositories import (
    AgentKnowledgeBaseRepository,
    ChunkIngest,
    DocumentRepository,
    KnowledgeBaseRepository,
)


@dataclass
class UseCasesBundle:
    """Container for all use cases needed by the CLI."""

    create_chat: CreateChatUseCase
    select_chat: SelectChatUseCase
    send_message: SendMessageUseCase
    view_settings: ViewSettingsUseCase
    change_settings: ChangeSettingsUseCase
    set_reranker_enabled: SetRerankerEnabledUseCase
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


@dataclass
class ChatInfo:
    """Информация о чате для отображения."""

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
class InvariantInfo:
    """Информация об инварианте для отображения."""

    id: int
    text: str
    created_at: datetime


class CreateChatUseCase:
    """Use case для создания нового чата."""

    def __init__(
        self,
        repository: AgentRepository,
        llm_provider: LlmProvider,
        task_profile_repository=None,
    ):
        self.repository = repository
        self.llm_provider = llm_provider
        self.task_profile_repository = task_profile_repository

    def execute(
        self,
        name: str,
        system_prompt: str | None,
        settings: AgentSettings,
        strategy: ContextWindowStrategy,
        task_profile_id: str | None = None,
        initial_phase: AgentPhase | None = None,
    ) -> Agent:
        """
        Создаёт новый чат с указанными настройками.

        Args:
            name: Название чата.
            system_prompt: Системный промпт (опционально).
            settings: Настройки агента.
            strategy: Стратегия управления контекстным окном.
            task_profile_id: UUID профиля задачи (опционально).
            initial_phase: Стартовая фаза агента (опционально, по умолчанию PLAN).

        Returns:
            Agent: Созданный агент.

        Raises:
            ValueError: Если указан несуществующий профиль задачи.
        """
        # Проверка существования профиля задачи, если он указан
        if task_profile_id is not None and self.task_profile_repository is not None:
            profile = self.task_profile_repository.get_profile_by_id(task_profile_id)
            if profile is None:
                raise ValueError(f"Профиль задачи с ID {task_profile_id} не найден")

        agent = self.repository.create_agent(
            name=name,
            initial_settings=settings,
            system_prompt=system_prompt,
            strategy=strategy,
            task_profile_id=task_profile_id,
            initial_phase=initial_phase,
        )
        return agent


class SelectChatUseCase:
    """Use case для выбора существующего чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def get_all_previews(self) -> list[AgentPreview]:
        """Получает список всех чатов."""
        return self.repository.get_all_previews()

    def get_agent(self, agent_id: int) -> Agent | None:
        """Получает агент по числовому ID."""
        return self.repository.get_agent(agent_id)


class SendMessageUseCase:
    """Use case для отправки сообщения и получения ответа."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent: Agent, user_message: str) -> tuple[LlmResponse, Agent]:
        """
        Отправляет сообщение агенту и получает ответ.

        Args:
            agent: Агент для общения.
            user_message: Текст сообщения пользователя.

        Returns:
            Tuple of (LlmResponse, updated Agent).

        Raises:
            ContextWindowExceededError: Если превышен лимит контекстного окна.
        """
        response = agent.continue_dialog(user_message)
        return response, agent


class ViewSettingsUseCase:
    """Use case для просмотра настроек чата."""

    def execute(self, agent: Agent | None) -> AgentSettings | None:
        """Получает настройки текущего агента."""
        if not agent:
            return None
        return agent.get_settings()


class ChangeSettingsUseCase:
    """Use case для изменения настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent: Agent, new_settings: AgentSettings) -> None:
        """
        Обновляет настройки агента.

        Args:
            agent: Агент для обновления.
            new_settings: Новые настройки.
        """
        agent.update_settings(new_settings)


class SetRerankerEnabledUseCase:
    """Use case включения/отключения реранкинга для конкретного чата."""

    def execute(self, agent: Agent, enabled: bool) -> bool:
        """Обновляет per-chat флаг реранкинга, сохраняя остальные настройки."""
        current = agent.get_settings()
        agent.update_settings(replace(current, reranker_enabled=bool(enabled)))
        return bool(enabled)


class ShowHistoryUseCase:
    """Use case для показа истории чата."""

    def execute(self, agent: Agent | None) -> list[Prompt] | None:
        """Получает историю сообщений агента."""
        if not agent:
            return None
        return agent.get_history()


class ShowSummaryUseCase:
    """Use case для показа саммари диалога."""

    def execute(self, agent: Agent | None) -> str | None:
        """
        Получает саммари из стратегии агента.

        Args:
            agent: Агент для получения саммари.

        Returns:
            Саммари или None, если оно отсутствует.
        """
        if not agent:
            return None

        strategy = agent.strategy
        if hasattr(strategy, "summary"):
            return strategy.summary
        return None


class ShowChatInfoUseCase:
    """Use case для показа информации о чате."""

    def execute(self, agent: Agent | None) -> ChatInfo | None:
        """
        Получает информацию о чате включая счетчики токенов.

        Args:
            agent: Агент для получения информации.

        Returns:
            ChatInfo или None, если агент не выбран.
        """
        if not agent:
            return None

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

        # Получаем текущую фазу агента
        current_phase = (
            agent.current_phase.value
            if hasattr(agent, "current_phase") and agent.current_phase
            else None
        )

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
            task_memory=agent.task_memory,
        )


class CreateBranchUseCase:
    """Use case для создания ветки текущего чата."""

    def execute(self, parent_agent: Agent, new_name: str | None = None) -> Agent:
        """
        Создаёт ветку текущего чата.

        Args:
            parent_agent: Родительский агент.
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """
        return parent_agent.branch(new_name=new_name)


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
        if selection.strategy_type == "DefaultStrategy":
            return DefaultStrategy()

        elif selection.strategy_type == "SummarizationStrategy":
            return SummarizationStrategy(
                non_compressible_count=selection.non_compressible_count or 2,
                buffer_size=selection.buffer_size or 3,
            )

        elif selection.strategy_type == "KeyValueMemoryStrategy":
            return KeyValueMemoryStrategy(
                non_compressible_count=selection.non_compressible_count or 2,
                buffer_size=selection.buffer_size or 3,
            )

        elif selection.strategy_type == "SlidingWindowStrategy":
            return SlidingWindowStrategy(
                window_size=selection.window_size or 10,
            )

        else:
            return DefaultStrategy()


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

    def __init__(self, global_memory_repository):
        self.global_memory_repository = global_memory_repository

    def execute(self, agent: Agent) -> None:
        """
        Загружает общесистемную память из репозитория.

        Args:
            agent: Агент, для которого нужно загрузить память.
        """
        agent.refresh_memory()


class SaveAgentMemoryUseCase:
    """Use case для сохранения памяти агента при выходе из чата."""

    def __init__(self, global_memory_repository):
        self.global_memory_repository = global_memory_repository

    def execute(self, agent: Agent) -> None:
        """
        Сохраняет общесистемную память о пользователе.

        Args:
            agent: Агент, для которого нужно сохранить память.
        """
        agent.save_memory()


class SaveUnsavedMemoriesUseCase:
    """Use case для сохранения всех несохранённых памятей при старте приложения."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self) -> None:
        """
        Находит все агенты с несохранёнными промптами и вызывает у них save_memory.

        Агент считается имеющим несохранённые промпты, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False
        """
        agents = self.repository.get_agents_with_unsaved_memory()

        for agent in agents:
            agent.save_memory()


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
        return [
            TaskProfileInfo(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                facts_count=len(p.facts),
                preferences=p.preferences or "",
                invariants_count=len(p.invariants),
            )
            for p in profiles
        ]


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
    ) -> TaskProfile:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.
            preferences: Инструкции и предпочтения пользователя (опционально).
            invariants: Список строгих правил/ограничений (опционально).

        Returns:
            TaskProfile: Созданный профиль.
        """
        return self.task_profile_repository.create_profile(
            name, description, preferences, invariants
        )


class GetTaskProfileMemoryUseCase:
    """Use case для просмотра памяти выбранного профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> TaskProfile | None:
        """
        Получает информацию о профиле задачи и его память.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            TaskProfile или None, если профиль не найден.
        """
        return self.task_profile_repository.get_profile_by_id(profile_id)


class DeleteTaskProfileUseCase:
    """Use case для удаления профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> bool:
        """
        Удаляет профиль задачи.

        Args:
            profile_id: UUID профиля для удаления.

        Returns:
            True, если профиль был удалён, False если не найден или привязан к агентам.
        """
        # Проверяем, привязан ли профиль к агентам
        if self.task_profile_repository.is_profile_linked_to_agents(profile_id):
            return False

        return self.task_profile_repository.delete_profile(profile_id)


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

    def execute(self, agent: Agent) -> list[McpServerStatus]:
        """Возвращает статусы всех подключённых к чату MCP-серверов.

        В список попадают и серверы, сохранённые в чате, но недоступные в
        данный момент (живое подключение не установлено или разорвано) —
        они отображаются с connected=False.
        """
        from mcp_client import MCP_MANAGER
        from mcp_registry import find_server

        connections = (
            MCP_MANAGER.get_connections(agent.agent_id)
            if agent.agent_id is not None
            else {}
        )
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

    def execute(self, agent: Agent) -> list:
        """Возвращает записи реестра McpServerInfo, не подключённые к чату."""
        from mcp_registry import get_available_servers

        return [
            server
            for server in get_available_servers()
            if server.name not in agent.connected_mcp_servers
        ]


class ConnectMcpUseCase:
    """Use case для подключения MCP-сервера к чату."""

    def execute(self, agent: Agent, server_name: str) -> tuple[bool, str]:
        """Подключает MCP-сервер к чату (см. Agent.connect_mcp)."""
        return agent.connect_mcp(server_name)


class DisconnectMcpUseCase:
    """Use case для отключения MCP-сервера от чата."""

    def execute(self, agent: Agent, server_name: str) -> tuple[bool, str]:
        """Отключает MCP-сервер от чата (см. Agent.disconnect_mcp)."""
        return agent.disconnect_mcp(server_name)


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
            settings=AgentSettings(),
            strategy=DefaultStrategy(),
            initial_phase=AgentPhase.EXECUTE,
        )

        # Подключаем MCP-серверы к freshly created чату: живые соединения
        # создаются в этом же процессе воркера, поэтому гарантированно
        # доступны агенту при вызове LLM с tools.
        for server_name in mcp_servers or []:
            success, message = self.connect_mcp.execute(agent, server_name)
            if not success:
                raise RuntimeError(
                    f"Не удалось подключить MCP-сервер '{server_name}' "
                    f"для периодического отчёта '{chat_name}': {message}"
                )

        response, agent = self.send_message.execute(agent, task)

        counters = agent.token_counters
        return ScheduledReport(
            chat_name=agent.name,
            agent_id=agent.agent_id,
            task=task,
            answer=response.content,
            prompt_tokens=counters.total_prompt_tokens,
            completion_tokens=counters.total_completion_tokens,
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

    def execute(self, agent: Agent, knowledge_base_id: int) -> tuple[bool, str]:
        if agent.agent_id is None:
            return False, "Агент ещё не сохранён — подключите базу знаний позже."

        kb = self._kb_repository.get(knowledge_base_id)
        if kb is None:
            return False, f"База знаний #{knowledge_base_id} не найдена."

        created = self._agent_kb_repository.attach(agent.agent_id, knowledge_base_id)
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

    def execute(self, agent: Agent, knowledge_base_id: int) -> tuple[bool, str]:
        if agent.agent_id is None:
            return False, "Агент ещё не сохранён."

        kb = self._kb_repository.get(knowledge_base_id)
        name = kb.name if kb is not None else f"#{knowledge_base_id}"

        removed = self._agent_kb_repository.detach(
            agent.agent_id, knowledge_base_id
        )
        if removed:
            return True, f"База знаний '{name}' отключена от чата."
        return True, f"База знаний '{name}' не была подключена к чату."


class ListAgentKnowledgeBasesUseCase:
    """Use case получения баз знаний, подключённых к чату."""

    def __init__(self, agent_knowledge_base_repository: AgentKnowledgeBaseRepository):
        self._agent_kb_repository = agent_knowledge_base_repository

    def execute(self, agent: Agent) -> list[KnowledgeBaseDTO]:
        if agent.agent_id is None:
            return []
        return self._agent_kb_repository.list_for_agent(agent.agent_id)


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
