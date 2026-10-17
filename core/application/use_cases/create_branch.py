from __future__ import annotations

from core.application.dtos.chat_dto import ChatDTO
from core.application.mappers.chat_mapper import _agent_to_chat_dto
from core.application.protocols.mcp_gateway import McpGateway
from core.application.use_cases._helpers.agent_access import _require_agent
from core.domain.protocols.agent_repository import AgentRepository


class CreateBranchUseCase:
    """Use case для создания ветки текущего чата."""

    def __init__(
        self, repository: AgentRepository, mcp_gateway: McpGateway | None = None
    ):
        self.repository = repository
        self._mcp_gateway = mcp_gateway

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
        branch = parent_agent.branch(new_name=new_name, repository=self.repository)

        # Переносим живые MCP-подключения на ветку (регистрация под новым ID)
        if (
            self._mcp_gateway is not None
            and parent_agent.agent_id is not None
            and branch.agent_id is not None
        ):
            connections = self._mcp_gateway.get_connections(parent_agent.agent_id)
            for server_name in branch.connected_mcp_servers:
                conn = connections.get(server_name)
                if conn is not None:
                    self._mcp_gateway.add_connection(
                        branch.agent_id, server_name, conn
                    )

        return _agent_to_chat_dto(branch)
