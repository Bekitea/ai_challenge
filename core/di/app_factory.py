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
from core.application.services.rag_model_service import RagModelService
from core.application.services.rag_service import RagService
from core.application.use_cases import (
    AddDocumentToKnowledgeBaseUseCase,
    AddInvariantUseCase,
    AttachKnowledgeBaseToAgentUseCase,
    ChangePhaseUseCase,
    ChangeSettingsUseCase,
    ConnectMcpUseCase,
    CreateApiKeyUseCase,
    CreateBranchUseCase,
    CreateChatUseCase,
    CreateKnowledgeBaseUseCase,
    CreateTaskProfileUseCase,
    DeleteApiKeyUseCase,
    DeleteDocumentUseCase,
    DeleteKnowledgeBaseUseCase,
    DeleteTaskProfileUseCase,
    DetachKnowledgeBaseFromAgentUseCase,
    DisconnectMcpUseCase,
    GetTaskProfileMemoryUseCase,
    ListAgentKnowledgeBasesUseCase,
    ListApiKeysUseCase,
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
    VerifyApiKeyUseCase,
    ViewGlobalMemoryUseCase,
    ViewSettingsUseCase,
)
from core.di.app_mode import get_mode_config
from core.infrastructure.embeddings.ollama_embedding_provider import (
    OllamaEmbeddingProvider,
)
from core.infrastructure.files.local_file_extractor import LocalFileExtractor
from core.infrastructure.llm.llm_provider_registry import LlmProviderRegistry
from core.infrastructure.llm.mock_llm_provider import MockLlmProvider
from core.infrastructure.llm.ollama_llm_provider import OllamaLlmProvider
from core.infrastructure.llm.yandex_cloud_llm_provider import YandexCloudLlmProvider
from core.infrastructure.mcp.mcp_manager_gateway import McpManagerGateway
from core.infrastructure.persistence.database_task_profile_repository import (
    DatabaseTaskProfileRepository,
)
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.file_global_memory_repository import (
    FileGlobalMemoryRepository,
)
from core.infrastructure.persistence.file_task_memory_repository import (
    FileTaskMemoryRepository,
)
from core.infrastructure.persistence.orm import Base
from core.infrastructure.persistence.persistent_agent_repository import (
    PersistentAgentRepository,
)
from core.infrastructure.persistence.sqlite_agent_knowledge_base_repository import (
    SqliteAgentKnowledgeBaseRepository,
)
from core.infrastructure.persistence.sqlite_api_key_repository import (
    DatabaseApiKeyRepository,
)
from core.infrastructure.persistence.sqlite_document_repository import (
    SqliteDocumentRepository,
)
from core.infrastructure.persistence.sqlite_knowledge_base_repository import (
    SqliteKnowledgeBaseRepository,
)
from core.infrastructure.persistence.sqlite_vec_vector_store import SqliteVecVectorStore
from core.infrastructure.reranking.http_reranker_provider import HttpRerankerProvider
from core.infrastructure.reranking.mock_reranker_provider import MockRerankerProvider


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
        from core.di.app_mode import validate_production_env

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

    knowledge_base_repository = SqliteKnowledgeBaseRepository(
        db_connection.get_session, vector_store
    )
    document_repository = SqliteDocumentRepository(
        db_connection.get_session, vector_store
    )
    agent_knowledge_base_repository = SqliteAgentKnowledgeBaseRepository(
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
        session_factory=db_connection.get_session,
        global_memory_repository=memory_repository,
        task_profile_repository=task_profile_repository,
        task_memory_repository=task_memory_repository,
    )

    # API-ключи доступа к REST API
    api_key_repository = DatabaseApiKeyRepository(db_connection.get_session)

    # Инфраструктурные адаптеры портов приложения
    mcp_gateway = McpManagerGateway()
    file_extractor = LocalFileExtractor()

    # Create and return all use cases
    create_chat = CreateChatUseCase(repository, task_profile_repository)
    send_message = SendMessageUseCase(
        repository, provider_registry, rag_service, mcp_gateway
    )
    connect_mcp = ConnectMcpUseCase(repository, mcp_gateway)

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
        create_branch=CreateBranchUseCase(repository, mcp_gateway),
        select_strategy=SelectContextStrategyUseCase(),
        view_global_memory=ViewGlobalMemoryUseCase(memory_repository),
        refresh_agent_memory=RefreshAgentMemoryUseCase(repository),
        save_agent_memory=SaveAgentMemoryUseCase(repository, provider_registry),
        save_unsaved_memories=SaveUnsavedMemoriesUseCase(
            repository, provider_registry
        ),
        list_task_profiles=ListTaskProfilesUseCase(task_profile_repository),
        create_task_profile=CreateTaskProfileUseCase(task_profile_repository),
        get_task_profile_memory=GetTaskProfileMemoryUseCase(task_profile_repository),
        delete_task_profile=DeleteTaskProfileUseCase(task_profile_repository),
        add_invariant=AddInvariantUseCase(task_profile_repository),
        remove_invariant=RemoveInvariantUseCase(task_profile_repository),
        list_invariants=ListInvariantsUseCase(task_profile_repository),
        connect_mcp=connect_mcp,
        disconnect_mcp=DisconnectMcpUseCase(repository, mcp_gateway),
        list_connected_mcp=ListConnectedMcpUseCase(repository, mcp_gateway),
        list_available_mcp=ListAvailableMcpUseCase(repository, mcp_gateway),
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
            knowledge_base_repository,
            document_repository,
            rag_model_service,
            file_extractor,
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
        create_api_key=CreateApiKeyUseCase(api_key_repository),
        list_api_keys=ListApiKeysUseCase(api_key_repository),
        delete_api_key=DeleteApiKeyUseCase(api_key_repository),
        verify_api_key=VerifyApiKeyUseCase(api_key_repository),
    )
