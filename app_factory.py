"""
Application Factory module for initializing application components.

This module encapsulates the initialization logic for all application components,
including LLM providers, repositories, and use cases. It abstracts away the
application mode (production vs test) from the CLI layer.
"""

from dataclasses import dataclass

from app_mode import get_mode_config
from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from llm_providers import MockLlmProvider, YandexCloudLlmProvider
from storage.agent_repositories import PersistentAgentRepository
from use_cases import (
    ChangeSettingsUseCase,
    CreateBranchUseCase,
    CreateChatUseCase,
    SelectChatUseCase,
    SelectContextStrategyUseCase,
    SendMessageUseCase,
    ShowChatInfoUseCase,
    ShowHistoryUseCase,
    ShowSummaryUseCase,
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

    # Initialize repository
    repository = PersistentAgentRepository(llm_provider)

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
        create_branch=CreateBranchUseCase(repository),
        select_strategy=SelectContextStrategyUseCase(),
    )
