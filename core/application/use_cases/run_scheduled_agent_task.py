from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from config import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_PROVIDER,
)
from core.application.dtos.scheduled_report import ScheduledReport
from core.application.dtos.settings_dto import SettingsDTO
from core.application.dtos.strategy_selection import StrategySelection

if TYPE_CHECKING:
    from core.application.use_cases.connect_mcp import ConnectMcpUseCase
    from core.application.use_cases.create_chat import CreateChatUseCase
    from core.application.use_cases.send_message import SendMessageUseCase


class RunScheduledAgentTaskUseCase:
    """Use case для выполнения периодической задачи агентом в новом чате.

    Инкапсулирует всю бизнес-логику сценария «отчёт по расписанию»:
    каждый запуск создаёт НОВЫЙ чат (переиспользование старого недопустимо:
    накопленная история контекста ломает периодические запросы), подключает
    в него необходимые MCP-серверы и отправляет агенту задание.

    Все зависимости передаются через конструктор фабрикой приложения
    (core.di.app_factory), поэтому Celery-слой общается с системой исключительно
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
            settings=SettingsDTO(
                provider=DEFAULT_REPORT_PROVIDER,
                model_id=DEFAULT_REPORT_MODEL,
            ),
            strategy_selection=StrategySelection(strategy_type="DefaultStrategy"),
            initial_phase="execute",
        )

        # Подключаем MCP-серверы к freshly created чату: живые соединения
        # создаются в этом же процессе воркера, поэтому гарантированно
        # доступны агенту при вызове LLM с tools.
        for server_name in mcp_servers or []:
            success, message = self.connect_mcp.execute(agent.agent_id, server_name)
            if not success:
                raise RuntimeError(
                    f"Не удалось подключить MCP-сервер '{server_name}' "
                    f"для периодического отчёта '{chat_name}': {message}"
                )

        response = self.send_message.execute(agent.agent_id, task)

        return ScheduledReport(
            chat_name=agent.name,
            agent_id=agent.agent_id,
            task=task,
            answer=response.content,
            prompt_tokens=response.total_prompt_tokens,
            completion_tokens=response.total_completion_tokens,
        )
