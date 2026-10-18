from __future__ import annotations

from core.application.exceptions import RagError
from core.application.use_cases.attach_knowledge_base_to_agent import (
    AttachKnowledgeBaseToAgentUseCase,
)
from core.application.use_cases.connect_mcp import ConnectMcpUseCase
from core.application.use_cases.list_agent_knowledge_bases import (
    ListAgentKnowledgeBasesUseCase,
)
from core.application.use_cases.list_knowledge_bases import (
    ListKnowledgeBasesUseCase,
)


class PrepareAssistantContextUseCase:
    """Готовит контекст ассистента: выделенная БЗ + один или несколько MCP-серверов.

    Используется командами ``/help`` (проектный ассистент), ``/support``
    (ассистент поддержки) и ``/files`` (ассистент по файлам): привязывает к чату
    выделенную базу знаний и идемпотентно подключает MCP-серверы. Возвращает
    информационные/предупредительные сообщения для вывода пользователю. Сбои не
    фатальны — команда продолжает работу и передаёт вопрос агенту.
    """

    def __init__(
        self,
        *,
        list_knowledge_bases: ListKnowledgeBasesUseCase,
        list_agent_knowledge_bases: ListAgentKnowledgeBasesUseCase,
        attach_knowledge_base: AttachKnowledgeBaseToAgentUseCase,
        connect_mcp: ConnectMcpUseCase,
        knowledge_base_name: str,
        knowledge_base_label: str,
        missing_kb_label: str,
        attach_error_subject: str,
        mcp_server_names: list[str],
    ):
        self._list_knowledge_bases = list_knowledge_bases
        self._list_agent_knowledge_bases = list_agent_knowledge_bases
        self._attach_knowledge_base = attach_knowledge_base
        self._connect_mcp = connect_mcp
        self._kb_name = knowledge_base_name
        self._kb_label = knowledge_base_label
        self._missing_kb_label = missing_kb_label
        self._attach_error_subject = attach_error_subject
        self._mcp_server_names = list(mcp_server_names)

    def execute(self, agent_id: int) -> list[str]:
        """Готовит контекст и возвращает сообщения для пользователя."""
        messages = self._ensure_knowledge_base(agent_id)
        for server_name in self._mcp_server_names:
            messages.extend(self._connect_mcp_server(agent_id, server_name))
        return messages

    def _ensure_knowledge_base(self, agent_id: int) -> list[str]:
        knowledge_base = None
        for kb in self._list_knowledge_bases.execute():
            if kb.name == self._kb_name:
                knowledge_base = kb
                break

        if knowledge_base is None:
            return [
                (
                    f"[WARN] {self._missing_kb_label} '{self._kb_name}' "
                    "не найдена. Засеять её можно в меню 'Базы знаний' (пункт 9)."
                )
            ]

        attached_ids = {
            kb.id for kb in self._list_agent_knowledge_bases.execute(agent_id)
        }
        if knowledge_base.id in attached_ids:
            return []

        try:
            self._attach_knowledge_base.execute(agent_id, knowledge_base.id)
        except RagError as exc:
            return [
                f"[WARN] Не удалось подключить {self._attach_error_subject}: {exc}"
            ]
        return [
            f"[INFO] {self._kb_label} '{self._kb_name}' подключена к чату."
        ]

    def _connect_mcp_server(self, agent_id: int, server_name: str) -> list[str]:
        try:
            success, message = self._connect_mcp.execute(agent_id, server_name)
        except Exception as exc:  # noqa: BLE001
            return [f"[WARN] Не удалось подключить {server_name} MCP: {exc}"]
        if success:
            return [f"[INFO] {message}"]
        return []
