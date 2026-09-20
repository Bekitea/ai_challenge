from dataclasses import dataclass

from app_mode import get_mode_config
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from llm_providers import MockLlmProvider, YandexCloudLlmProvider
from storage.agent_repositories import PersistentAgentRepository
from storage.db_connection import DatabaseConnection
from storage.global_memory_repository import FileGlobalMemoryRepository
from storage.orm_models import Base
from storage.task_profile_repository import FileTaskProfileRepository
from use_cases import (
    ChangeSettingsUseCase,
    CreateBranchUseCase,
    CreateChatUseCase,
    CreateTaskProfileUseCase,
    DeleteTaskProfileUseCase,
    GetTaskProfileMemoryUseCase,
    ListTaskProfilesUseCase,
    RefreshAgentMemoryUseCase,
    SaveAgentMemoryUseCase,
    SaveUnsavedMemoriesUseCase,
    SelectChatUseCase,
    SelectContextStrategyUseCase,
    SendMessageUseCase,
    ShowChatInfoUseCase,
    ShowHistoryUseCase,
    ShowSummaryUseCase,
    ViewGlobalMemoryUseCase,
    ViewSettingsUseCase,
)


@dataclass
class UseCasesBundle:
    """Container for all use cases needed by the CLI."""

    create_chat: CreateChatUseCase
    select_chat: SelectChatUseCase
    send_message: SendMessageUseCase
    view_settings: ViewSettingsUseCase
    change_settings: ChangeSettingsUseCase
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

    # Create LLM provider based on mode
    if mode_config.use_mock_provider:
        llm_provider = MockLlmProvider()
    else:
        llm_provider = YandexCloudLlmProvider(
            api_key=YANDEX_API_KEY,
            folder_id=YANDEX_FOLDER_ID,
        )

    # Initialize database connection and tables
    db_connection = DatabaseConnection(
        connect_args={"check_same_thread": False, "timeout": 30}
    )
    db_connection.init_tables(Base.metadata)

    # Initialize global memory repository
    from config import GLOBAL_MEMORY_PATH
    memory_repository = FileGlobalMemoryRepository(GLOBAL_MEMORY_PATH)

    # Initialize task profile repository
    from config import FILE_STORAGE_DIR
    task_profile_repository = FileTaskProfileRepository(FILE_STORAGE_DIR, db_connection.get_session)

    # Initialize repository with session factory
    repository = PersistentAgentRepository(
        llm_provider=llm_provider,
        session_factory=db_connection.get_session,
        global_memory_repository=memory_repository,
        task_profile_repository=task_profile_repository,
    )

    # Create and return all use cases
    return UseCasesBundle(
        create_chat=CreateChatUseCase(repository, llm_provider),
        select_chat=SelectChatUseCase(repository),
        send_message=SendMessageUseCase(repository),
        view_settings=ViewSettingsUseCase(),
        change_settings=ChangeSettingsUseCase(repository),
        show_history=ShowHistoryUseCase(),
        show_summary=ShowSummaryUseCase(),
        show_chat_info=ShowChatInfoUseCase(),
        create_branch=CreateBranchUseCase(),
        select_strategy=SelectContextStrategyUseCase(),
        view_global_memory=ViewGlobalMemoryUseCase(memory_repository),
        refresh_agent_memory=RefreshAgentMemoryUseCase(memory_repository),
        save_agent_memory=SaveAgentMemoryUseCase(memory_repository),
        save_unsaved_memories=SaveUnsavedMemoriesUseCase(repository),
        list_task_profiles=ListTaskProfilesUseCase(task_profile_repository),
        create_task_profile=CreateTaskProfileUseCase(task_profile_repository),
        get_task_profile_memory=GetTaskProfileMemoryUseCase(task_profile_repository),
        delete_task_profile=DeleteTaskProfileUseCase(task_profile_repository),
    )
