from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, ClassVar
from uuid import uuid4

from config import (
    MEMORY_LLM_MAX_RETRIES,
    MEMORY_LLM_TIMEOUT,
    TASK_MEMORY_ENABLED,
    TASK_MEMORY_UPDATE_EVERY_N_MESSAGES,
    TASK_MEMORY_WINDOW_MESSAGES,
)
from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.llm_response import LlmResponse
from core.domain.dtos.prompt import Prompt
from core.domain.dtos.prompt_sources import PromptSources
from core.domain.dtos.rag_retrieval_result import RagRetrievalResult
from core.domain.dtos.task_memory import TaskMemory
from core.domain.dtos.task_profile import TaskProfile
from core.domain.dtos.token_counters import TokenCounters
from core.domain.dtos.tool_call_record import ToolCallRecord
from core.domain.entities.agent_phase import AgentPhase
from core.domain.entities.context_strategy_factory import create_strategy_from_dict
from core.domain.entities.context_window_strategy import ContextWindowStrategy
from core.domain.entities.default_strategy import DefaultStrategy
from core.domain.entities.prompt_builder import PromptBuilder
from core.domain.exceptions.agent_persistence_error import AgentPersistenceError
from core.domain.exceptions.context_window_exceeded_error import (
    ContextWindowExceededError,
)
from core.domain.exceptions.history_access_error import HistoryAccessError
from core.domain.exceptions.llm_timeout_error import LlmTimeoutError
from core.domain.exceptions.memory_access_error import MemoryAccessError
from core.domain.protocols.agent_repository import AgentRepository
from core.domain.protocols.llm_provider import LlmProvider
from core.domain.protocols.tool_executor import ToolExecutor

logger = logging.getLogger("agent.rag")


class Agent:
    """Агент для ведения диалога с пользователем через LLM.

    Домен-сущность: хранит только собственное состояние и знает о
    репозитории, LLM-провайдере и исполнителе инструментов исключительно
    через аргументы методов. Персистентность памяти и истории делегируется
    репозиторию, переданному в метод; при его отсутствии агент падает
    fail-fast с доменным исключением ``AgentPersistenceError``.
    """

    MAX_MCP_TOOL_ITERATIONS = 5  # защита от бесконечного цикла tool calling

    def __init__(
        self,
        agent_id: int | None,
        name: str,
        conversation_id: str | None,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        messages: list[Prompt] | None = None,
        strategy: ContextWindowStrategy | None = None,
        task_profile: TaskProfile | None = None,
        connected_mcp_servers: list[str] | None = None,
        initial_phase: AgentPhase | None = None,
        prompt_builder: PromptBuilder | None = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.conversation_id = conversation_id
        self._settings = initial_settings or AgentSettings()
        self._messages: list[Prompt] = messages if messages is not None else []
        self._strategy = strategy or DefaultStrategy()
        self._prompt_builder = prompt_builder or PromptBuilder()

        # Global memory fields
        self.global_memory = GlobalMemory()
        self.is_dialog_remembered = False

        # Task profile fields
        self.task_profile = task_profile

        # Память задачи текущего диалога (per-chat, по conversation_id).
        self.task_memory = TaskMemory()
        self._turns_since_task_memory = 0

        # Phase state (default to PLAN; non-interactive chats such as
        # scheduled reports may start directly in EXECUTE).
        self._current_phase = initial_phase or AgentPhase.PLAN

        # Подключённые к чату MCP-серверы (машинные имена).
        self.connected_mcp_servers: list[str] = list(connected_mcp_servers or [])

        # Добавляем системный промпт только если сообщений ещё нет
        if system_prompt and not self._messages:
            self._messages.append(Prompt(role="system", content=system_prompt))

        self._last_message_timestamp: datetime | None = None
        self._token_counters = TokenCounters()

    # ------------------------------------------------------------------
    # Persistence guards (fail-fast)
    # ------------------------------------------------------------------

    @staticmethod
    def _require_repository(
        repository: AgentRepository | None,
    ) -> AgentRepository:
        """Возвращает репозиторий или падает fail-fast.

        Память и история чата хранятся репозиторием; без него доступ к ним
        невозможен, поэтому агент не деградирует молча, а бросает доменное
        исключение.
        """
        if repository is None:
            raise AgentPersistenceError(
                "Репозиторий агента не передан — доступ к памяти и истории "
                "чата невозможен."
            )
        return repository

    def _require_conversation_id(self) -> str:
        """Возвращает conversation_id или падает fail-fast, если он не задан."""
        if self.conversation_id is None:
            raise AgentPersistenceError(
                f"У чата '{self.name}' отсутствует conversation_id — доступ к "
                "истории и памяти задачи невозможен."
            )
        return self.conversation_id

    # ------------------------------------------------------------------
    # Свойства / состояние
    # ------------------------------------------------------------------

    @property
    def token_counters(self) -> TokenCounters:
        """Возвращает счетчики токенов."""
        return self._token_counters

    @property
    def strategy(self) -> ContextWindowStrategy:
        """Возвращает стратегию управления контекстным окном."""
        return self._strategy

    def set_strategy(self, strategy: ContextWindowStrategy) -> None:
        """Устанавливает стратегию управления контекстным окном."""
        self._strategy = strategy

    @property
    def turns_since_task_memory(self) -> int:
        """Счётчик ходов с последнего обновления памяти задачи.

        Персистится в репозитории, чтобы каденция обновления памяти задачи
        сохранялась между загрузками агента (CLI грузит агента на каждый
        запрос по ``agent_id``).
        """
        return self._turns_since_task_memory

    @turns_since_task_memory.setter
    def turns_since_task_memory(self, value: int) -> None:
        self._turns_since_task_memory = value

    def get_settings(self) -> AgentSettings:
        """Возвращает текущие настройки агента."""
        return self._settings

    def _technical_model_id(self) -> str | None:
        """Модель для служебных запросов к LLM (память, факты, суммаризация).

        Служебные запросы используют ту же модель, что выбрана для чата.
        Если модель не задана, запрос выполнять нельзя — вернётся ``None``.
        """
        model_id = self._settings.model_id
        if model_id is None:
            logger.warning(
                "Служебный запрос к LLM пропущен: у чата не выбрана модель."
            )
        return model_id

    def update_settings(
        self, new_settings: AgentSettings, repository: AgentRepository
    ) -> None:
        """Обновляет настройки агента и сохраняет состояние."""
        self._settings = new_settings
        self.save(repository)

    def get_history(self) -> list[Prompt]:
        """Возвращает всю историю диалога (включая системный промпт)."""
        return self._messages.copy()

    # ------------------------------------------------------------------
    # MCP-состояние (без знания об инфраструктуре MCP)
    # ------------------------------------------------------------------

    def attach_mcp_server(
        self, server_name: str, repository: AgentRepository
    ) -> None:
        """Добавляет имя подключённого MCP-сервера и сохраняет чат."""
        if server_name not in self.connected_mcp_servers:
            self.connected_mcp_servers.append(server_name)
        self.save(repository)

    def detach_mcp_server(
        self, server_name: str, repository: AgentRepository
    ) -> None:
        """Убирает имя MCP-сервера из списка и сохраняет чат."""
        if server_name in self.connected_mcp_servers:
            self.connected_mcp_servers.remove(server_name)
        self.save(repository)

    # ------------------------------------------------------------------
    # Сохранение / память
    # ------------------------------------------------------------------

    def save(self, repository: AgentRepository) -> None:
        """Сохраняет состояние агента (метаданные и историю) через репозиторий."""
        repository = self._require_repository(repository)
        try:
            repository.update_agent(self)
        except AgentPersistenceError:
            raise
        except Exception as e:
            raise HistoryAccessError(
                f"Не удалось сохранить состояние/историю чата '{self.name}': {e}"
            ) from e

    def refresh_memory(self, repository: AgentRepository) -> None:
        """Загружает общесистемную память и память задачи из репозитория.

        Вызывается перед операциями, которые читают или изменяют память.
        """
        repository = self._require_repository(repository)
        try:
            self.global_memory = repository.get_global_memory()
            self.task_memory = self._load_task_memory(repository)
        except AgentPersistenceError:
            raise
        except Exception as e:
            raise MemoryAccessError(
                f"Не удалось загрузить память чата '{self.name}': {e}"
            ) from e

    def _load_task_memory(self, repository: AgentRepository) -> TaskMemory:
        """Загружает память задачи текущего диалога из репозитория."""
        conversation_id = self._require_conversation_id()
        memory = repository.get_task_memory(conversation_id)
        return memory if memory is not None else TaskMemory()

    def _save_task_memory(self, repository: AgentRepository) -> None:
        """Сохраняет память задачи текущего диалога через репозиторий."""
        repository = self._require_repository(repository)
        conversation_id = self._require_conversation_id()
        self.task_memory.updated_at = datetime.now().astimezone()
        try:
            repository.save_task_memory(conversation_id, self.task_memory)
        except AgentPersistenceError:
            raise
        except Exception as e:
            raise MemoryAccessError(
                f"Не удалось сохранить память задачи чата '{self.name}': {e}"
            ) from e

    # ------------------------------------------------------------------
    # Диалог
    # ------------------------------------------------------------------

    def continue_dialog(
        self,
        user_prompt: str,
        *,
        repository: AgentRepository,
        llm_provider: LlmProvider,
        rag_result: RagRetrievalResult | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        on_memory_warning: Callable[[str], None] | None = None,
    ) -> LlmResponse:
        """
        Продолжает диалог: добавляет сообщение пользователя, делает запрос к LLM,
        сохраняет ответ и возвращает результат.

        Args:
            user_prompt: Текст сообщения от пользователя.
            repository: Репозиторий агента (память и история).
            llm_provider: Выбранный LLM-провайдер для этого запроса.
            rag_result: Заранее поднятый RAG-контекст (None — RAG не задействован).
            tools: Готовые OpenAI-описания инструментов (None — без инструментов).
            tool_executor: Исполнитель tool-вызовов (обязателен, если модель
                запрашивает инструменты).
            on_memory_warning: Необязательный колбэк для сообщений о сбое
                обновления памяти задачи диалога (не прерывает диалог).

        Returns:
            LlmResponse: Ответ от LLM с контентом и reasoning.

        Raises:
            AgentPersistenceError: Если репозиторий недоступен.
            ContextWindowExceededError: Если prompt_tokens превысил размер
                контекстного окна.
        """
        repository = self._require_repository(repository)
        self.refresh_memory(repository)

        # Добавляем сообщение пользователя
        user_timestamp = datetime.now().astimezone()
        user_message = Prompt(
            role="user",
            content=user_prompt,
            timestamp=user_timestamp,
        )
        self._messages.append(user_message)
        self._last_message_timestamp = user_timestamp

        if rag_result is None:
            rag_result = RagRetrievalResult(chunks=[], has_knowledge_bases=False)

        # Подготавливаем сообщения через PromptBuilder: он централизованно
        # подмешивает память, профиль задачи, RAG-контекст и фазу, а стратегия
        # управляет только контекстным окном.
        sources = PromptSources(
            global_facts=list(self.global_memory.facts),
            task_profile=self.task_profile,
            phase_description=self._current_phase.get_description(),
            rag_context=rag_result.chunks,
            rag_enabled=rag_result.has_knowledge_bases,
            task_memory=self.task_memory,
        )
        prepared = self._prompt_builder.build(
            history=self._messages,
            sources=sources,
            strategy=self._strategy,
            llm_provider=llm_provider,
            model_id=self._settings.model_id,
        )

        messages_for_llm = prepared.messages
        settings = self._settings
        kwargs = settings.to_llm_request_properties()

        if tools:
            kwargs["tools"] = tools

        # Делаем запрос к LLM
        response = llm_provider.generate(messages=messages_for_llm, **kwargs)

        # === Цикл tool calling: модель может просить вызвать инструменты ===
        for _ in range(self.MAX_MCP_TOOL_ITERATIONS):
            if not response.tool_calls:
                break
            if tool_executor is None:
                raise ValueError(
                    "Модель запросила вызов инструмента, но tool_executor не "
                    "передан агенту."
                )

            # Временный хвост протокола (assistant с tool_calls + результаты
            # инструментов). Он НЕ попадает в постоянную историю и не
            # сохраняется, пока группа не станет полной и не получит ответ —
            # так прерывание процесса между запросами не может оставить в
            # сохранённой истории «битый» неполный протокол (400 missing
            # field tool_call_id при следующем запуске).
            pending: list[dict[str, Any]] = [
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": (
                                    call.arguments
                                    if isinstance(call.arguments, str)
                                    else json.dumps(call.arguments or {})
                                ),
                            },
                        }
                        for call in response.tool_calls
                    ],
                }
            ]

            # Вызываем каждый инструмент и добавляем результаты как role="tool"
            for call in response.tool_calls:
                tool_result = tool_executor.execute(call)
                pending.append(
                    {
                        "role": "tool",
                        "content": tool_result,
                        "tool_call_id": call.id,
                        "name": call.name,
                    }
                )

            # Повторный запрос к LLM уже с результатами инструментов:
            # постоянная история (уже очищенная стратегией) + временный хвост.
            followup_messages = messages_for_llm + pending
            response = llm_provider.generate(messages=followup_messages, **kwargs)

            # Ответ получен — группа завершена, переносим её в историю.
            for entry in pending:
                if entry["role"] == "assistant":
                    self._messages.append(
                        Prompt(
                            role="assistant",
                            content=entry.get("content") or "",
                            timestamp=datetime.now().astimezone(),
                            reasoning=response.reasoning,
                            prompt_tokens=response.prompt_tokens,
                            completion_tokens=response.completion_tokens,
                            tool_calls=[
                                ToolCallRecord(
                                    id=tc["id"],
                                    name=tc["function"]["name"],
                                    arguments=tc["function"]["arguments"],
                                )
                                for tc in entry["tool_calls"]
                            ],
                        )
                    )
                else:
                    self._messages.append(
                        Prompt(
                            role="tool",
                            content=entry["content"],
                            timestamp=datetime.now().astimezone(),
                            tool_call_id=entry["tool_call_id"],
                            name=entry.get("name"),
                        )
                    )
            pending = []

        # Проверяем лимит контекстного окна (только для assistant prompt)
        context_window_size = (
            settings.context_window_size or 200_000
        )  # По умолчанию 200k
        if (
            response.prompt_tokens is not None
            and response.prompt_tokens > context_window_size
        ):
            raise ContextWindowExceededError(
                f"Превышен лимит контекстного окна: {response.prompt_tokens} токенов (лимит: {context_window_size})"
            )

        # Обновляем счетчики токенов
        # Сначала обновляем счетчики от суммаризации (если была)
        if prepared.summarization_tokens:
            tech_prompt, tech_completion = prepared.summarization_tokens
            self._token_counters.tech_prompt_tokens += tech_prompt
            self._token_counters.tech_completion_tokens += tech_completion

        # Затем обновляем счетчики от основного (пользовательского) запроса
        if response.prompt_tokens is not None:
            self._token_counters.chat_prompt_tokens += response.prompt_tokens

        if response.completion_tokens is not None:
            self._token_counters.chat_completion_tokens += response.completion_tokens

        # Источники RAG для отображения в клиенте: None, если у чата нет
        # подключённых баз знаний; пустой список — базы есть, но ни один
        # чанк не прошёл порог релевантности.
        response.rag_sources = (
            rag_result.chunks if rag_result.has_knowledge_bases else None
        )

        # Сохраняем ответ ассистента
        assistant_timestamp = datetime.now().astimezone()
        assistant_message = Prompt(
            role="assistant",
            content=response.content,
            timestamp=assistant_timestamp,
            reasoning=response.reasoning,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            settings=AgentSettings(
                model_id=settings.model_id,
                provider=settings.provider,
                top_k=settings.top_k,
                top_p=settings.top_p,
                temperature=settings.temperature,
                reasoning_effort=settings.reasoning_effort,
                context_window_size=settings.context_window_size,
            ),
        )
        self._messages.append(assistant_message)
        self._last_message_timestamp = assistant_timestamp

        # Помечаем диалог как непрошедший через сохранение памяти
        self.is_dialog_remembered = False

        # Память задачи: обновляем по счётчику ходов или сразу после сжатия
        # контекста, чтобы цель диалога не терялась на длинных диалогах.
        self._maybe_update_task_memory(
            compressed=bool(prepared.summarization_tokens),
            repository=repository,
            llm_provider=llm_provider,
            on_warning=on_memory_warning,
        )

        # Автосохранение после каждого сообщения
        self.save(repository)

        return response

    @property
    def last_message_timestamp(self) -> datetime | None:
        """Возвращает временную метку последнего сообщения."""
        return self._last_message_timestamp

    @property
    def message_count(self) -> int:
        """Возвращает количество сообщений (без системного промпта и
        технических сообщений протокола tool calling — assistant с tool_calls
        и role="tool")."""
        return len(
            [
                msg
                for msg in self._messages
                if msg.role not in ("system", "tool") and not msg.tool_calls
            ]
        )

    def get_last_message_preview(self, max_length: int = 50) -> str | None:
        """Возвращает превью последнего сообщения пользователя или агента."""
        visible_messages = [
            msg
            for msg in self._messages
            if msg.role not in ("system", "tool") and not msg.tool_calls
        ]
        if not visible_messages:
            return None

        last_msg = visible_messages[-1]
        preview = last_msg.content[:max_length]
        if len(last_msg.content) > max_length:
            preview += "..."
        return preview

    def branch(
        self,
        new_name: str | None = None,
        repository: AgentRepository | None = None,
    ) -> Agent:
        """
        Создаёт нового агента-ветку на основе текущего.

        Копируются настройки, вся история сообщений, счетчики токенов и стратегия.
        Ветка получает новый conversation_id (UUID) для отдельного хранения истории.

        Args:
            new_name: Новое название для ветки (опционально).
            repository: Репозиторий для сохранения новой ветки.

        Returns:
            Agent: Новый агент-ветка.
        """
        repository = self._require_repository(repository)

        if not new_name:
            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            new_name = f"{self.name} (branch {timestamp})"

        current_settings = self.get_settings()
        current_history = self.get_history()
        current_strategy = self.strategy
        new_strategy = create_strategy_from_dict(current_strategy.to_dict())

        branched_agent = Agent(
            agent_id=None,
            conversation_id=str(uuid4()),
            name=new_name,
            initial_settings=current_settings,
            system_prompt=None,
            messages=current_history.copy(),
            strategy=new_strategy,
            # Ветка — чистый лист по памяти задачи (новый conversation_id).
            task_profile=self.task_profile,
            connected_mcp_servers=list(self.connected_mcp_servers),
        )

        # Глобальная память общая для всех чатов — переносим факты.
        branched_agent.global_memory = GlobalMemory(
            facts=list(self.global_memory.facts)
        )

        current_counters = self.token_counters
        branched_agent._token_counters.chat_prompt_tokens = (
            current_counters.chat_prompt_tokens
        )
        branched_agent._token_counters.chat_completion_tokens = (
            current_counters.chat_completion_tokens
        )
        branched_agent._token_counters.tech_prompt_tokens = (
            current_counters.tech_prompt_tokens
        )
        branched_agent._token_counters.tech_completion_tokens = (
            current_counters.tech_completion_tokens
        )

        if current_history:
            non_system_msgs = [m for m in current_history if m.role != "system"]
            if non_system_msgs:
                branched_agent._last_message_timestamp = non_system_msgs[-1].timestamp

        branched_agent.save(repository)

        return branched_agent

    # ------------------------------------------------------------------
    # Память задачи
    # ------------------------------------------------------------------

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        """Нормализует значение из JSON в список непустых строк."""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _maybe_update_task_memory(
        self,
        compressed: bool,
        *,
        repository: AgentRepository,
        llm_provider: LlmProvider,
        on_warning: Callable[[str], None] | None = None,
    ) -> None:
        """Триггерит обновление памяти задачи по счётчику или при сжатии.

        Это внутридиалоговая каденция. На выходе из чата память задачи
        обновляется отдельно и безусловно (см. ``save_memory``).
        """
        if not TASK_MEMORY_ENABLED:
            return
        self._turns_since_task_memory += 1
        if (
            compressed
            or self._turns_since_task_memory >= TASK_MEMORY_UPDATE_EVERY_N_MESSAGES
        ):
            self.update_task_memory(
                repository=repository,
                llm_provider=llm_provider,
                on_warning=on_warning,
            )
            self._turns_since_task_memory = 0

    def update_task_memory(
        self,
        *,
        repository: AgentRepository,
        llm_provider: LlmProvider,
        on_warning: Callable[[str], None] | None = None,
    ) -> bool:
        """Обновляет память задачи текущего диалога через LLM.

        Отправляет ограниченное окно последних сообщений вместе с текущей
        памятью и просит вернуть полное актуальное состояние: новые
        уточнения пользователя заменяют устаревшие. Расход токенов пишется
        в ``tech_prompt_tokens``/``tech_completion_tokens``.

        При сбое запроса к модели (включая таймаут) память не меняется, а
        сообщение об ошибке передаётся в ``on_warning`` (если задан) — диалог
        не прерывается.

        Returns:
            True, если обновление прервано таймаутом модели; иначе False.
        """
        if not TASK_MEMORY_ENABLED:
            return False
        self._require_repository(repository)
        self._require_conversation_id()

        window = [
            msg for msg in self._messages if msg.role in ("user", "assistant")
        ][-TASK_MEMORY_WINDOW_MESSAGES:]
        if not window:
            return False

        model_id = self._technical_model_id()
        if model_id is None:
            return False

        dialog_text = ""
        for msg in window:
            role_ru = "Пользователь" if msg.role == "user" else "Ассистент"
            dialog_text += f"{role_ru}: {msg.content}\n"

        current_memory = json.dumps(
            {
                "goal": self.task_memory.goal,
                "constraints": self.task_memory.constraints,
                "terms": self.task_memory.terms,
                "clarifications": self.task_memory.clarifications,
            },
            ensure_ascii=False,
        )

        profile_context = ""
        if self.task_profile is not None:
            profile_context = (
                f"\nКонтекст профиля задачи «{self.task_profile.name}»: "
                f"{self.task_profile.description}\n"
            )

        system_prompt = (
            "Ты ведёшь память задачи диалога и возвращаешь её в формате JSON.\n"
            "Поля:\n"
            '- "goal": основная цель диалога одной строкой;\n'
            '- "constraints": список зафиксированных ограничений и требований;\n'
            '- "terms": список зафиксированных терминов и их значений '
            "(формат «термин — значение»);\n"
            '- "clarifications": список уже внесённых пользователем уточнений '
            "и принятых решений.\n\n"
            "Правила:\n"
            "1. Верни ПОЛНОЕ актуальное состояние памяти, а не только новое.\n"
            "2. Если пользователь уточнил или изменил ранее сказанное — "
            "замени устаревшее значение новым.\n"
            "3. Не дублируй записи и не выдумывай данные, которых нет в диалоге.\n"
            "4. Сохраняй ранее зафиксированные ограничения и термины, пока "
            "пользователь их не изменит.\n"
            f"{profile_context}\n"
            f"Текущая память (JSON):\n{current_memory}\n\n"
            f"Диалог для анализа:\n{dialog_text}\n\n"
            'Верни JSON строго со схемой: {"goal": "...", "constraints": [...], '
            '"terms": [...], "clarifications": [...]}'
        )

        try:
            response = llm_provider.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Обнови память задачи."},
                ],
                temperature=0.1,
                max_tokens=1000,
                timeout=MEMORY_LLM_TIMEOUT,
                max_retries=MEMORY_LLM_MAX_RETRIES,
                response_format={"type": "json_object"},
                model_id=model_id,
            )
        except LlmTimeoutError as e:
            if on_warning is not None:
                on_warning(f"Не удалось обновить память задачи: {e}")
            return True
        except Exception as e:  # noqa: BLE001 — сбой модели не прерывает диалог
            if on_warning is not None:
                on_warning(f"Не удалось обновить память задачи: {e}")
            return False

        if response.prompt_tokens is not None:
            self._token_counters.tech_prompt_tokens += response.prompt_tokens
        if response.completion_tokens is not None:
            self._token_counters.tech_completion_tokens += response.completion_tokens

        try:
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            return False
        if not isinstance(parsed, dict):
            return False

        recognized = {"goal", "constraints", "terms", "clarifications"}
        if not recognized & parsed.keys():
            return False

        self.task_memory = TaskMemory(
            goal=(
                str(parsed["goal"]).strip()
                if "goal" in parsed
                else self.task_memory.goal
            ),
            constraints=(
                self._as_str_list(parsed["constraints"])
                if "constraints" in parsed
                else self.task_memory.constraints
            ),
            terms=(
                self._as_str_list(parsed["terms"])
                if "terms" in parsed
                else self.task_memory.terms
            ),
            clarifications=(
                self._as_str_list(parsed["clarifications"])
                if "clarifications" in parsed
                else self.task_memory.clarifications
            ),
        )
        self._save_task_memory(repository)
        return False

    def save_memory(
        self,
        *,
        repository: AgentRepository,
        llm_provider: LlmProvider,
        on_warning: Callable[[str], None] | None = None,
    ) -> None:
        """
        Сохраняет общесистемную память о пользователе и память задачи.

        Память задачи обновляется здесь всегда — это финальный flush при
        выходе из чата (и при старте приложения для несохранённых чатов). Он
        НЕ подчиняется порогу ``TASK_MEMORY_UPDATE_EVERY_N_MESSAGES``: порог
        управляет только каденцией обновлений *во время* диалога (см.
        ``_maybe_update_task_memory``). Поэтому для короткого чата (меньше
        порога ходов) ``/info`` до выхода ещё показывает пустую память, а
        персистентное состояние после выхода уже содержит извлечённую память —
        это ожидаемое поведение.

        Если is_dialog_remembered == False:
        1. Достает все промпты с is_remembered == False
        2. Отправляет их в ЛЛМ для получения новых фактов:
           - Для глобальной памяти: факты о личности пользователя
           - Для памяти задачи: факты, относящиеся к задаче (если агент привязан к профилю)
        3. Объединяет старые и новые факты
        4. Сохраняет через репозиторий
        5. Помечает все промпты и агент как remembered

        Расход токенов записывается в tech_prompt_tokens и tech_completion_tokens.
        Сбой обновления памяти задачи диалога передаётся в ``on_warning`` и не
        прерывает извлечение глобальной и профильной памяти.
        """
        repository = self._require_repository(repository)
        self._require_conversation_id()

        if self.is_dialog_remembered:
            return  # Нечего сохранять

        # Загружаем актуальное состояние памяти, чтобы не потерять его при merge.
        self.refresh_memory(repository)

        # Находим все промпты с is_remembered == False (только user и assistant)
        unremembered_prompts = [
            msg
            for msg in self._messages
            if not msg.is_remembered and msg.role in ("user", "assistant")
        ]

        if not unremembered_prompts:
            return  # Нет новых данных для запоминания

        model_id = self._technical_model_id()
        if model_id is None:
            return

        # Финальный flush памяти задачи при выходе (перекрывающая семантика).
        # Выполняется независимо от порога TASK_MEMORY_UPDATE_EVERY_N_MESSAGES:
        # порог управляет только каденцией обновлений во время диалога
        # (_maybe_update_task_memory). Если этот вызов упал по таймауту,
        # остальные вызовы памяти для чата не выполняем — прерываем
        # сохранение, чтобы не ждать ещё раз.
        task_memory_timed_out = self.update_task_memory(
            repository=repository,
            llm_provider=llm_provider,
            on_warning=on_warning,
        )
        self._turns_since_task_memory = 0
        if task_memory_timed_out:
            raise LlmTimeoutError("Таймаут обновления памяти задачи.")

        dialog_text = ""
        for msg in unremembered_prompts:
            role_ru = "Пользователь" if msg.role == "user" else "Ассистент"
            dialog_text += f"{role_ru}: {msg.content}\n"

        # === Сохранение глобальной памяти (факты о пользователе) ===
        old_facts_text = ""
        if self.global_memory.facts:
            old_facts_text = "Текущие факты о пользователе:\n" + "\n".join(
                f"- {f}" for f in self.global_memory.facts
            )

        global_system_prompt = (
            "Ты ассистент для извлечения фактов о пользователе из диалога. "
            "Твоя задача — найти новую информацию о пользователе (предпочтения, факты биографии, интересы и т.д.) "
            "и вернуть её в формате JSON.\n\n"
            "Важные правила:\n"
            "1. Возвращай ТОЛЬКО новые факты, которых нет в текущем списке.\n"
            "2. Игнорируй противоречия — просто добавляй новые факты.\n"
            "3. Факты должны быть краткими и конкретными.\n"
            "4. Если новых фактов нет, верни пустой список.\n\n"
            f"{old_facts_text}\n\n"
            f"Диалог для анализа:\n{dialog_text}\n\n"
            "Верни ответ в формате JSON со схемой: "
            '{"facts": ["факт 1", "факт 2", ...]}'
        )

        messages_for_llm = [
            {"role": "system", "content": global_system_prompt},
            {
                "role": "user",
                "content": "Извлеки факты о пользователе из диалога выше.",
            },
        ]

        response = llm_provider.generate(
            messages=messages_for_llm,
            temperature=0.1,
            max_tokens=1000,
            timeout=MEMORY_LLM_TIMEOUT,
            max_retries=MEMORY_LLM_MAX_RETRIES,
            response_format={"type": "json_object"},
            model_id=model_id,
        )

        # Обновляем счетчики технических токенов
        if response.prompt_tokens is not None:
            self._token_counters.tech_prompt_tokens += response.prompt_tokens
        if response.completion_tokens is not None:
            self._token_counters.tech_completion_tokens += response.completion_tokens

        try:
            result = json.loads(response.content)
            new_global_facts = result.get("facts", [])
        except json.JSONDecodeError:
            new_global_facts = []

        all_global_facts = list(self.global_memory.facts)
        for fact in new_global_facts:
            if fact not in all_global_facts:
                all_global_facts.append(fact)

        self.global_memory.facts = all_global_facts
        try:
            repository.save_global_memory(self.global_memory)
        except AgentPersistenceError:
            raise
        except Exception as e:
            raise MemoryAccessError(
                f"Не удалось сохранить глобальную память: {e}"
            ) from e

        # === Сохранение памяти задачи (если агент привязан к профилю) ===
        if self.task_profile and self.task_profile.id:
            task_old_facts_text = ""
            if self.task_profile.facts:
                task_old_facts_text = (
                    f'Текущие факты о задаче "{self.task_profile.name}":\n'
                    + "\n".join(f"- {f}" for f in self.task_profile.facts)
                )

            task_system_prompt = (
                f"Ты ассистент для извлечения фактов о задаче из диалога. "
                f"Задача: {self.task_profile.name}. Описание: {self.task_profile.description}.\n"
                "Твоя задача — найти новую информацию, относящуюся к задаче (прогресс, решения, ограничения, требования, результаты) "
                "и вернуть её в формате JSON.\n\n"
                "Важные правила:\n"
                "1. Возвращай ТОЛЬКО новые факты, которых нет в текущем списке.\n"
                "2. Игнорируй противоречия — просто добавляй новые факты.\n"
                "3. Факты должны быть краткими и конкретными.\n"
                "4. Если новых фактов нет, верни пустой список.\n"
                "5. Извлекай только факты, относящиеся к задаче, а не к пользователю.\n\n"
                f"{task_old_facts_text}\n\n"
                f"Диалог для анализа:\n{dialog_text}\n\n"
                "Верни ответ в формате JSON со схемой: "
                '{"facts": ["факт 1", "факт 2", ...]}'
            )

            messages_for_task_llm = [
                {"role": "system", "content": task_system_prompt},
                {"role": "user", "content": "Извлеки факты о задаче из диалога выше."},
            ]

            task_response = llm_provider.generate(
                messages=messages_for_task_llm,
                temperature=0.1,
                max_tokens=1000,
                timeout=MEMORY_LLM_TIMEOUT,
                max_retries=MEMORY_LLM_MAX_RETRIES,
                response_format={"type": "json_object"},
                model_id=model_id,
            )

            # Обновляем счетчики технических токенов
            if task_response.prompt_tokens is not None:
                self._token_counters.tech_prompt_tokens += task_response.prompt_tokens
            if task_response.completion_tokens is not None:
                self._token_counters.tech_completion_tokens += (
                    task_response.completion_tokens
                )

            try:
                task_result = json.loads(task_response.content)
                new_task_facts = task_result.get("facts", [])
            except json.JSONDecodeError:
                new_task_facts = []

            all_task_facts = list(self.task_profile.facts)
            for fact in new_task_facts:
                if fact not in all_task_facts:
                    all_task_facts.append(fact)

            self.task_profile.facts = all_task_facts
            try:
                repository.save_task_profile_facts(
                    self.task_profile.id, all_task_facts
                )
            except AgentPersistenceError:
                raise
            except Exception as e:
                raise MemoryAccessError(
                    f"Не удалось сохранить факты профиля задачи: {e}"
                ) from e

        # Помечаем все промпты как remembered
        for msg in self._messages:
            msg.is_remembered = True

        # Помечаем агента как remembered
        self.is_dialog_remembered = True

    # ------------------------------------------------------------------
    # Фазы
    # ------------------------------------------------------------------

    @property
    def current_phase(self) -> AgentPhase:
        """Возвращает текущую фазу работы агента."""
        return self._current_phase

    _PHASE_ORDER: ClassVar[list[AgentPhase]] = [
        AgentPhase.PLAN,
        AgentPhase.EXECUTE,
        AgentPhase.VALIDATE,
        AgentPhase.REPORT,
    ]

    def set_phase(
        self, phase: AgentPhase, repository: AgentRepository
    ) -> None:
        """
        Устанавливает новую фазу работы агента.

        Raises:
            ValueError: Если переход запрещен (перескок этапа вперед).
        """
        old_phase = self._current_phase

        # Можно перейти на следующий этап или на любой предыдущий.
        # Нельзя перескакивать этапы вперед.
        old_index = self._PHASE_ORDER.index(old_phase)
        new_index = self._PHASE_ORDER.index(phase)

        if new_index > old_index and new_index != old_index + 1:
            raise ValueError(
                f"Нельзя перескочить этап: переход из {old_phase.name} сразу в {phase.name} запрещен"
            )

        self._current_phase = phase
        self.save(repository)

    def handle_phase_command(
        self, command: str, repository: AgentRepository
    ) -> tuple[bool, str]:
        """
        Обрабатывает команды перехода по фазам.

        Args:
            command: Команда (/plan, /execute, /validate, /report)
            repository: Репозиторий агента для сохранения состояния.

        Returns:
            Кортеж (успех, сообщение)
        """
        command_map = {
            "/plan": AgentPhase.PLAN,
            "/execute": AgentPhase.EXECUTE,
            "/validate": AgentPhase.VALIDATE,
            "/report": AgentPhase.REPORT,
        }

        if command.lower() not in command_map:
            return False, f"Неизвестная команда: {command}"

        new_phase = command_map[command.lower()]
        old_phase = self._current_phase

        old_index = self._PHASE_ORDER.index(old_phase)
        new_index = self._PHASE_ORDER.index(new_phase)

        if new_index > old_index and new_index != old_index + 1:
            return (
                False,
                f"Нельзя перескочить этап: переход из {old_phase.name} сразу в {new_phase.name} запрещен",
            )

        self._current_phase = new_phase

        self.save(repository)

        return True, f"Фаза изменена: {old_phase.name} -> {new_phase.name}"
