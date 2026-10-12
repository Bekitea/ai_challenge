from app_mode import get_mode_config
from config import (
    EMBEDDING_BASE_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_TIMEOUT,
    FILE_STORAGE_DIR,
    RAG_CANDIDATE_LIMIT_TOTAL,
    RAG_FINAL_TOP_K,
    RAG_RELEVANCE_THRESHOLD,
    RAG_VECTOR_TOP_K_PER_KB,
    RERANKER_BASE_URL,
    RERANKER_BATCH_SIZE,
    RERANKER_ENABLED,
    RERANKER_MODEL_NAME,
    RERANKER_RETRY_COUNT,
    RERANKER_TIMEOUT,
    YANDEX_API_KEY,
    YANDEX_FOLDER_ID,
)
from embedding_providers import OllamaEmbeddingProvider
from llm_providers import (
    LlmProviderRegistry,
    MockLlmProvider,
    OllamaLlmProvider,
    YandexCloudLlmProvider,
)
from rag_service import RagModelService, RagService
from reranker_providers import HttpRerankerProvider, MockRerankerProvider
from storage.agent_repositories import PersistentAgentRepository
from storage.db_connection import DatabaseConnection
from storage.global_memory_repository import FileGlobalMemoryRepository
from storage.orm_models import Base
from storage.rag_repositories import (
    AgentKnowledgeBaseRepository,
    DocumentRepository,
    KnowledgeBaseRepository,
)
from storage.task_memory_repository import FileTaskMemoryRepository
from storage.task_profile_repository import (
    DatabaseTaskProfileRepository,
)
from storage.vector_store import SqliteVecVectorStore
from use_cases import (
    AddDocumentToKnowledgeBaseUseCase,
    AddInvariantUseCase,
    AttachKnowledgeBaseToAgentUseCase,
    ChangePhaseUseCase,
    ChangeSettingsUseCase,
    ConnectMcpUseCase,
    CreateBranchUseCase,
    CreateChatUseCase,
    CreateKnowledgeBaseUseCase,
    CreateTaskProfileUseCase,
    DeleteDocumentUseCase,
    DeleteKnowledgeBaseUseCase,
    DeleteTaskProfileUseCase,
    DetachKnowledgeBaseFromAgentUseCase,
    DisconnectMcpUseCase,
    GetTaskProfileMemoryUseCase,
    ListAgentKnowledgeBasesUseCase,
    ListAvailableMcpUseCase,
    ListConnectedMcpUseCase,
    ListDocumentChunksUseCase,
    ListDocumentsUseCase,
    ListInvariantsUseCase,
    ListKnowledgeBasesUseCase,
    ListModelsUseCase,
    ListTaskProfilesUseCase,
    RefreshAgentMemoryUseCase,
    RemoveInvariantUseCase,
    RetrieveRagContextUseCase,
    RunScheduledAgentTaskUseCase,
    SaveAgentMemoryUseCase,
    SaveUnsavedMemoriesUseCase,
    SearchKnowledgeBaseUseCase,
    SelectChatUseCase,
    SelectContextStrategyUseCase,
    SendMessageUseCase,
    SetRerankerEnabledUseCase,
    ShowChatInfoUseCase,
    ShowHistoryUseCase,
    ShowSummaryUseCase,
    UseCasesBundle,
    ViewGlobalMemoryUseCase,
    ViewSettingsUseCase,
)


def initialize_application() -> UseCasesBundle:
    """
    Initialize all application components based on the current mode.

    This function:
    1. Determines the application mode (production or test)
    2. Creates the appropriate LLM provider
    3. Validates environment variables if in production mode
    4. Initializes the repository
    5. Creates and returns all use cases

    Returns:
        UseCasesBundle: A container with all initialized use cases.

    Raises:
        OSError: If production mode is selected but required environment
                 variables are not set.
    """
    mode_config = get_mode_config()

    # Validate production environment if needed
    if mode_config.require_env_vars:
        from app_mode import validate_production_env

        validate_production_env(YANDEX_API_KEY, YANDEX_FOLDER_ID)

    # Create LLM provider registry. В тестовом режиме — детерминированные
    # моки (yandex + ollama); в проде/локальном — реальные провайдеры.
    # Ollama доступен всегда, Yandex регистрируется только при наличии ключей
    # (в PROD они уже проверены выше, в LOCAL — опциональны). Провайдер для
    # конкретного чата выбирается по AgentSettings.provider.
    if mode_config.use_mock_provider:
        provider_registry = LlmProviderRegistry(
            {
                "yandex": MockLlmProvider("yandex"),
                "ollama": MockLlmProvider("ollama"),
            }
        )
    else:
        providers = {"ollama": OllamaLlmProvider()}
        if YANDEX_API_KEY and YANDEX_FOLDER_ID:
            providers["yandex"] = YandexCloudLlmProvider(
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID,
            )
        provider_registry = LlmProviderRegistry(providers)

    # Initialize database connection and tables
    db_connection = DatabaseConnection(
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    db_connection.init_tables(Base.metadata)

    # Initialize global memory repository
    from config import GLOBAL_MEMORY_PATH

    memory_repository = FileGlobalMemoryRepository(GLOBAL_MEMORY_PATH)

    # Initialize task profile repository
    task_profile_repository = DatabaseTaskProfileRepository(
        FILE_STORAGE_DIR, db_connection.get_session
    )

    # Память задачи диалога (per-chat, файловое хранилище)
    task_memory_repository = FileTaskMemoryRepository(FILE_STORAGE_DIR)

    # Инициализация RAG-подсистемы (эмбеддер, векторное хранилище, репозитории)
    vector_store = SqliteVecVectorStore(db_connection.get_session)
    embedder = OllamaEmbeddingProvider(
        base_url=EMBEDDING_BASE_URL,
        model_name=EMBEDDING_MODEL_NAME,
        dimension=EMBEDDING_DIMENSION,
        batch_size=EMBEDDING_BATCH_SIZE,
        timeout=EMBEDDING_TIMEOUT,
    )
    # Реранкер: в тестовом режиме — детерминированный мок без сети;
    # в проде — HTTP-сервис (reranker_service/) при RERANKER_ENABLED.
    if mode_config.use_mock_provider:
        reranker = MockRerankerProvider(model_name=RERANKER_MODEL_NAME)
    elif RERANKER_ENABLED:
        reranker = HttpRerankerProvider(
            base_url=RERANKER_BASE_URL,
            model_name=RERANKER_MODEL_NAME,
            batch_size=RERANKER_BATCH_SIZE,
            timeout=RERANKER_TIMEOUT,
            retry_count=RERANKER_RETRY_COUNT,
        )
    else:
        reranker = None
    rag_model_service = RagModelService(embedder=embedder, reranker=reranker)

    knowledge_base_repository = KnowledgeBaseRepository(
        db_connection.get_session, vector_store
    )
    document_repository = DocumentRepository(
        db_connection.get_session, vector_store
    )
    agent_knowledge_base_repository = AgentKnowledgeBaseRepository(
        db_connection.get_session
    )
    rag_service = RagService(
        model_service=rag_model_service,
        knowledge_base_repository=knowledge_base_repository,
        document_repository=document_repository,
        agent_knowledge_base_repository=agent_knowledge_base_repository,
        vector_store=vector_store,
        vector_top_k_per_kb=RAG_VECTOR_TOP_K_PER_KB,
        candidate_limit_total=RAG_CANDIDATE_LIMIT_TOTAL,
        final_top_k=RAG_FINAL_TOP_K,
        reranker_enabled=RERANKER_ENABLED,
        relevance_threshold=RAG_RELEVANCE_THRESHOLD,
    )

    # Initialize repository with session factory
    repository = PersistentAgentRepository(
        llm_provider_registry=provider_registry,
        session_factory=db_connection.get_session,
        global_memory_repository=memory_repository,
        task_profile_repository=task_profile_repository,
        rag_service=rag_service,
        task_memory_repository=task_memory_repository,
    )

    # Create and return all use cases
    create_chat = CreateChatUseCase(repository, task_profile_repository)
    send_message = SendMessageUseCase(repository)
    connect_mcp = ConnectMcpUseCase(repository)

    return UseCasesBundle(
        create_chat=create_chat,
        select_chat=SelectChatUseCase(repository),
        send_message=send_message,
        view_settings=ViewSettingsUseCase(repository),
        change_settings=ChangeSettingsUseCase(repository),
        set_reranker_enabled=SetRerankerEnabledUseCase(repository),
        change_phase=ChangePhaseUseCase(repository),
        list_models=ListModelsUseCase(provider_registry),
        show_history=ShowHistoryUseCase(repository),
        show_summary=ShowSummaryUseCase(repository),
        show_chat_info=ShowChatInfoUseCase(repository),
        create_branch=CreateBranchUseCase(repository),
        select_strategy=SelectContextStrategyUseCase(),
        view_global_memory=ViewGlobalMemoryUseCase(memory_repository),
        refresh_agent_memory=RefreshAgentMemoryUseCase(repository),
        save_agent_memory=SaveAgentMemoryUseCase(repository),
        save_unsaved_memories=SaveUnsavedMemoriesUseCase(repository),
        list_task_profiles=ListTaskProfilesUseCase(task_profile_repository),
        create_task_profile=CreateTaskProfileUseCase(task_profile_repository),
        get_task_profile_memory=GetTaskProfileMemoryUseCase(task_profile_repository),
        delete_task_profile=DeleteTaskProfileUseCase(task_profile_repository),
        add_invariant=AddInvariantUseCase(task_profile_repository),
        remove_invariant=RemoveInvariantUseCase(task_profile_repository),
        list_invariants=ListInvariantsUseCase(task_profile_repository),
        connect_mcp=connect_mcp,
        disconnect_mcp=DisconnectMcpUseCase(repository),
        list_connected_mcp=ListConnectedMcpUseCase(repository),
        list_available_mcp=ListAvailableMcpUseCase(repository),
        run_scheduled_agent_task=RunScheduledAgentTaskUseCase(
            create_chat=create_chat,
            send_message=send_message,
            connect_mcp=connect_mcp,
        ),
        create_knowledge_base=CreateKnowledgeBaseUseCase(
            knowledge_base_repository, rag_model_service
        ),
        delete_knowledge_base=DeleteKnowledgeBaseUseCase(
            knowledge_base_repository
        ),
        list_knowledge_bases=ListKnowledgeBasesUseCase(knowledge_base_repository),
        add_document=AddDocumentToKnowledgeBaseUseCase(
            knowledge_base_repository, document_repository, rag_model_service
        ),
        list_documents=ListDocumentsUseCase(
            knowledge_base_repository, document_repository
        ),
        list_document_chunks=ListDocumentChunksUseCase(document_repository),
        delete_document=DeleteDocumentUseCase(document_repository),
        attach_knowledge_base=AttachKnowledgeBaseToAgentUseCase(
            knowledge_base_repository, agent_knowledge_base_repository
        ),
        detach_knowledge_base=DetachKnowledgeBaseFromAgentUseCase(
            knowledge_base_repository, agent_knowledge_base_repository
        ),
        list_agent_knowledge_bases=ListAgentKnowledgeBasesUseCase(
            agent_knowledge_base_repository
        ),
        retrieve_rag_context=RetrieveRagContextUseCase(rag_service),
        search_knowledge_base=SearchKnowledgeBaseUseCase(rag_service),
    )
