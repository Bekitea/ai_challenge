from __future__ import annotations

from collections.abc import Callable

from core.application.adapters.mcp_tool_executor import McpToolExecutor
from core.application.adapters.mcp_tools import collect_mcp_tools
from core.application.dtos.message_response_dto import MessageResponseDTO
from core.application.mappers.response_mapper import _response_to_dto
from core.application.protocols.llm_registry import LlmRegistry
from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _require_agent
from core.application.use_cases._helpers.llm_provider_resolver import (
    _resolve_llm_provider,
)
from core.application.use_cases._helpers.rag_context import _retrieve_rag_context
from core.domain.protocols.agent_repository import AgentRepository
from core.domain.protocols.rag_retriever import RagRetriever


class SendMessageUseCase:
    """Use case для отправки сообщения и получения ответа."""

    def __init__(
        self,
        repository: AgentRepository,
        registry: LlmRegistry,
        rag_service: RagRetriever | None = None,
        mcp_gateway: McpGateway | None = None,
    ):
        self.repository = repository
        self._registry = registry
        self._rag_service = rag_service
        self._mcp_gateway = mcp_gateway

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

        tools: list[dict] = []
        tool_executor = None
        if self._mcp_gateway is not None and agent.agent_id is not None:
            tools = collect_mcp_tools(
                self._mcp_gateway,
                agent.agent_id,
                agent.connected_mcp_servers,
                agent.name,
            )
            if tools:
                tool_executor = McpToolExecutor(self._mcp_gateway, agent.agent_id)

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
