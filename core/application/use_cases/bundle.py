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
    from core.application.use_cases.change_phase import ChangePhaseUseCase
    from core.application.use_cases.change_settings import ChangeSettingsUseCase
    from core.application.use_cases.connect_mcp import ConnectMcpUseCase
    from core.application.use_cases.create_api_key import CreateApiKeyUseCase
    from core.application.use_cases.create_branch import CreateBranchUseCase
    from core.application.use_cases.create_chat import CreateChatUseCase
    from core.application.use_cases.create_knowledge_base import (
        CreateKnowledgeBaseUseCase,
    )
    from core.application.use_cases.create_task_profile import (
        CreateTaskProfileUseCase,
    )
    from core.application.use_cases.delete_api_key import DeleteApiKeyUseCase
    from core.application.use_cases.delete_document import DeleteDocumentUseCase
    from core.application.use_cases.delete_knowledge_base import (
        DeleteKnowledgeBaseUseCase,
    )
    from core.application.use_cases.delete_task_profile import (
        DeleteTaskProfileUseCase,
    )
    from core.application.use_cases.detach_knowledge_base_from_agent import (
        DetachKnowledgeBaseFromAgentUseCase,
    )
    from core.application.use_cases.disconnect_mcp import DisconnectMcpUseCase
    from core.application.use_cases.get_task_profile_memory import (
        GetTaskProfileMemoryUseCase,
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
    from core.application.use_cases.list_task_profiles import (
        ListTaskProfilesUseCase,
    )
    from core.application.use_cases.prepare_assistant_context import (
        PrepareAssistantContextUseCase,
    )
    from core.application.use_cases.refresh_agent_memory import (
        RefreshAgentMemoryUseCase,
    )
    from core.application.use_cases.remove_invariant import RemoveInvariantUseCase
    from core.application.use_cases.retrieve_rag_context import (
        RetrieveRagContextUseCase,
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
    from core.application.use_cases.show_chat_info import ShowChatInfoUseCase
    from core.application.use_cases.show_history import ShowHistoryUseCase
    from core.application.use_cases.show_summary import ShowSummaryUseCase
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
    create_api_key: CreateApiKeyUseCase
    list_api_keys: ListApiKeysUseCase
    delete_api_key: DeleteApiKeyUseCase
    verify_api_key: VerifyApiKeyUseCase
