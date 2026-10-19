from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.application.use_cases.add_document_to_knowledge_base import (
        AddDocumentToKnowledgeBaseUseCase,
    )
    from core.application.use_cases.add_invariant import AddInvariantUseCase
    from core.application.use_cases.attach_knowledge_base_to_agent import (
        AttachKnowledgeBaseToAgentUseCase,
    )
    from core.application.use_cases.bind_research_library import (
        BindResearchLibraryUseCase,
    )
    from core.application.use_cases.build_hypothesis_context import (
        BuildHypothesisContextUseCase,
    )
    from core.application.use_cases.build_review_context import (
        BuildReviewContextUseCase,
    )
    from core.application.use_cases.change_phase import ChangePhaseUseCase
    from core.application.use_cases.change_settings import ChangeSettingsUseCase
    from core.application.use_cases.connect_mcp import ConnectMcpUseCase
    from core.application.use_cases.create_api_key import CreateApiKeyUseCase
    from core.application.use_cases.create_branch import CreateBranchUseCase
    from core.application.use_cases.create_chat import CreateChatUseCase
    from core.application.use_cases.create_knowledge_base import (
        CreateKnowledgeBaseUseCase,
    )
    from core.application.use_cases.create_research_library import (
        CreateResearchLibraryUseCase,
    )
    from core.application.use_cases.create_task_profile import (
        CreateTaskProfileUseCase,
    )
    from core.application.use_cases.delete_api_key import DeleteApiKeyUseCase
    from core.application.use_cases.delete_document import DeleteDocumentUseCase
    from core.application.use_cases.delete_knowledge_base import (
        DeleteKnowledgeBaseUseCase,
    )
    from core.application.use_cases.delete_research_library import (
        DeleteResearchLibraryUseCase,
    )
    from core.application.use_cases.delete_task_profile import (
        DeleteTaskProfileUseCase,
    )
    from core.application.use_cases.detach_knowledge_base_from_agent import (
        DetachKnowledgeBaseFromAgentUseCase,
    )
    from core.application.use_cases.detach_research_library import (
        DetachResearchLibraryUseCase,
    )
    from core.application.use_cases.disconnect_mcp import DisconnectMcpUseCase
    from core.application.use_cases.ensure_preset_task_profiles import (
        EnsurePresetTaskProfilesUseCase,
    )
    from core.application.use_cases.ensure_research_library import (
        EnsureResearchLibraryUseCase,
    )
    from core.application.use_cases.get_active_research_library import (
        GetActiveResearchLibraryUseCase,
    )
    from core.application.use_cases.get_research_article import (
        GetResearchArticleUseCase,
    )
    from core.application.use_cases.get_research_library_stats import (
        GetResearchLibraryStatsUseCase,
    )
    from core.application.use_cases.get_task_profile_memory import (
        GetTaskProfileMemoryUseCase,
    )
    from core.application.use_cases.import_research_articles import (
        ImportResearchArticlesUseCase,
    )
    from core.application.use_cases.list_agent_knowledge_bases import (
        ListAgentKnowledgeBasesUseCase,
    )
    from core.application.use_cases.list_api_keys import ListApiKeysUseCase
    from core.application.use_cases.list_available_mcp import (
        ListAvailableMcpUseCase,
    )
    from core.application.use_cases.list_connected_mcp import (
        ListConnectedMcpUseCase,
    )
    from core.application.use_cases.list_document_chunks import (
        ListDocumentChunksUseCase,
    )
    from core.application.use_cases.list_documents import ListDocumentsUseCase
    from core.application.use_cases.list_invariants import ListInvariantsUseCase
    from core.application.use_cases.list_knowledge_bases import (
        ListKnowledgeBasesUseCase,
    )
    from core.application.use_cases.list_models import ListModelsUseCase
    from core.application.use_cases.list_research_articles import (
        ListResearchArticlesUseCase,
    )
    from core.application.use_cases.list_research_libraries import (
        ListResearchLibrariesUseCase,
    )
    from core.application.use_cases.list_research_library_articles import (
        ListResearchLibraryArticlesUseCase,
    )
    from core.application.use_cases.list_task_profiles import (
        ListTaskProfilesUseCase,
    )
    from core.application.use_cases.prepare_assistant_context import (
        PrepareAssistantContextUseCase,
    )
    from core.application.use_cases.recommend_research_articles import (
        RecommendResearchArticlesUseCase,
    )
    from core.application.use_cases.refresh_agent_memory import (
        RefreshAgentMemoryUseCase,
    )
    from core.application.use_cases.remove_invariant import RemoveInvariantUseCase
    from core.application.use_cases.retrieve_rag_context import (
        RetrieveRagContextUseCase,
    )
    from core.application.use_cases.review_pull_request import (
        ReviewPullRequestUseCase,
    )
    from core.application.use_cases.run_file_assistant import (
        RunFileAssistantUseCase,
    )
    from core.application.use_cases.run_scheduled_agent_task import (
        RunScheduledAgentTaskUseCase,
    )
    from core.application.use_cases.save_agent_memory import SaveAgentMemoryUseCase
    from core.application.use_cases.save_unsaved_memories import (
        SaveUnsavedMemoriesUseCase,
    )
    from core.application.use_cases.search_knowledge_base import (
        SearchKnowledgeBaseUseCase,
    )
    from core.application.use_cases.search_research_articles import (
        SearchResearchArticlesUseCase,
    )
    from core.application.use_cases.search_research_library import (
        SearchResearchLibraryUseCase,
    )
    from core.application.use_cases.seed_project_knowledge_base import (
        SeedProjectKnowledgeBaseUseCase,
    )
    from core.application.use_cases.select_chat import SelectChatUseCase
    from core.application.use_cases.select_context_strategy import (
        SelectContextStrategyUseCase,
    )
    from core.application.use_cases.send_message import SendMessageUseCase
    from core.application.use_cases.set_reranker_enabled import (
        SetRerankerEnabledUseCase,
    )
    from core.application.use_cases.set_task_profile_mcp_servers import (
        SetTaskProfileMcpServersUseCase,
    )
    from core.application.use_cases.show_chat_info import ShowChatInfoUseCase
    from core.application.use_cases.show_history import ShowHistoryUseCase
    from core.application.use_cases.show_summary import ShowSummaryUseCase
    from core.application.use_cases.summarize_research_articles import (
        SummarizeResearchArticlesUseCase,
    )
    from core.application.use_cases.switch_research_library import (
        SwitchResearchLibraryUseCase,
    )
    from core.application.use_cases.update_research_library_profile import (
        UpdateResearchLibraryProfileUseCase,
    )
    from core.application.use_cases.verify_api_key import VerifyApiKeyUseCase
    from core.application.use_cases.view_global_memory import (
        ViewGlobalMemoryUseCase,
    )
    from core.application.use_cases.view_settings import ViewSettingsUseCase


@dataclass
class UseCasesBundle:
    """Единый контейнер всех use cases для слоёв представления.

    Единственное определение в проекте: его импортирует и
    ``core.di.app_factory`` (создаёт), и слои представления
    (``core.presentation.*``) (потребляют). Поля описаны
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
    set_task_profile_mcp_servers: SetTaskProfileMcpServersUseCase
    ensure_preset_task_profiles: EnsurePresetTaskProfilesUseCase
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
    seed_project_knowledge_base: SeedProjectKnowledgeBaseUseCase
    prepare_project_context: PrepareAssistantContextUseCase
    prepare_support_context: PrepareAssistantContextUseCase
    run_file_assistant: RunFileAssistantUseCase
    seed_support_knowledge_base: SeedProjectKnowledgeBaseUseCase
    review_pull_request: ReviewPullRequestUseCase
    seed_review_knowledge_base: SeedProjectKnowledgeBaseUseCase
    research_create_library: CreateResearchLibraryUseCase
    research_ensure_library: EnsureResearchLibraryUseCase
    research_bind_library: BindResearchLibraryUseCase
    research_detach_library: DetachResearchLibraryUseCase
    research_delete_library: DeleteResearchLibraryUseCase
    research_get_active_library: GetActiveResearchLibraryUseCase
    research_list_libraries: ListResearchLibrariesUseCase
    research_switch_library: SwitchResearchLibraryUseCase
    research_update_profile: UpdateResearchLibraryProfileUseCase
    research_search_articles: SearchResearchArticlesUseCase
    research_import_articles: ImportResearchArticlesUseCase
    research_list_articles: ListResearchArticlesUseCase
    research_list_library_articles: ListResearchLibraryArticlesUseCase
    research_get_article: GetResearchArticleUseCase
    research_stats: GetResearchLibraryStatsUseCase
    research_summarize_articles: SummarizeResearchArticlesUseCase
    research_search_library: SearchResearchLibraryUseCase
    research_recommend_articles: RecommendResearchArticlesUseCase
    research_review_context: BuildReviewContextUseCase
    research_hypothesis_context: BuildHypothesisContextUseCase
    create_api_key: CreateApiKeyUseCase
    list_api_keys: ListApiKeysUseCase
    delete_api_key: DeleteApiKeyUseCase
    verify_api_key: VerifyApiKeyUseCase
