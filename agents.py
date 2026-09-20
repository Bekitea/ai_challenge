from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
)
from llm_providers import LlmProvider, LlmResponse


class ContextWindowExceededError(Exception):
    """Исключение, выбрасываемое при превышении лимита контекстного окна."""


@dataclass
class AgentSettings:
    """Настройки агента для взаимодействия с LLM."""

    model_id: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения."""
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "reasoning_effort": self.reasoning_effort,
                "context_window_size": self.context_window_size,
            }.items()
            if v is not None
        }

    def to_llm_request_properties(self) -> dict[str, Any]:
        """Преобразует настройки в словарь, отфильтровывая None значения."""
        return {
            k: v
            for k, v in {
                "model_id": self.model_id,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "temperature": self.temperature,
                "reasoning_effort": self.reasoning_effort,
            }.items()
            if v is not None
        }


@dataclass
class TokenCounters:
    """Счетчики токенов для чата."""

    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    tech_prompt_tokens: int = 0
    tech_completion_tokens: int = 0

    @property
    def total_prompt_tokens(self) -> int:
        """Общее количество prompt_tokens."""
        return self.chat_prompt_tokens + self.tech_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Общее количество completion_tokens."""
        return self.chat_completion_tokens + self.tech_completion_tokens


@dataclass
class Prompt:
    """Сообщение в диалоге с агентом."""

    role: str  # "system", "user", "assistant"
    content: str
    timestamp: datetime | None = (
        None  # None для system, обязательно для user и assistant
    )
    reasoning: str | None = None  # Только для assistant
    settings: AgentSettings | None = (
        None  # Только для assistant (настройки на момент генерации)
    )
    prompt_tokens: int | None = None  # Только для assistant
    completion_tokens: int | None = None  # Только для assistant
    is_remembered: bool = False  # Пометка о прохождении через сохранение памяти


@dataclass
class GlobalMemory:
    """Общесистемная память о пользователе."""

    facts: list[str] = field(default_factory=list)


@dataclass
class TaskProfile:
    """Профиль задачи с памятью о фактах задачи."""
    id: str
    name: str
    description: str
    created_at: datetime | None
    facts: list[str] = field(default_factory=list)
    preferences: str = ""


@dataclass
class AgentPreview:
    """Превью агента для отображения в списке."""

    agent_id: int
    name: str
    last_message_timestamp: datetime | None
    message_count: int
    last_message_preview: str | None = None


class Agent:
    """Агент для ведения диалога с пользователем через LLM."""

    def __init__(
        self,
        agent_id: int | None,
        name: str,
        llm_provider: LlmProvider,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        history_storage: Any | None = None,
        messages: list[Prompt] | None = None,
        strategy: ContextWindowStrategy | None = None,
        auto_save: bool = True,
        conversation_id: str | None = None,
        global_memory_repository: Any | None = None,
        task_profile: TaskProfile | None = None,
        task_profile_repository: Any | None = None,
    ):
        if llm_provider is None:
            raise ValueError("llm_provider is required")
        if global_memory_repository is None:
            raise ValueError("global_memory_repository is required")
        if task_profile_repository is None:
            raise ValueError("task_profile_repository is required")
        if conversation_id is None:
            raise ValueError("conversation_id is required")
        if history_storage is None:
            raise ValueError("history_storage is required")

        self._llm_provider = llm_provider
        self._repository = None  # Устанавливается при регистрации в репозитории
        self._global_memory_repository = global_memory_repository
        self._task_profile_repository = task_profile_repository
        self.conversation_id = conversation_id  # UUID для связи с файловым хранилищем
        self._history_storage = history_storage

        self.agent_id = agent_id
        self.name = name
        self._settings = initial_settings or AgentSettings()
        self._messages: list[Prompt] = messages if messages is not None else []
        self._strategy = strategy or DefaultStrategy()
        self._auto_save = auto_save

        # Global memory fields
        self.global_memory = GlobalMemory()
        self.is_dialog_remembered = False

        # Task profile fields
        self.task_profile = task_profile

        # Добавляем системный промпт только если сообщений ещё нет
        if system_prompt and not self._messages:
            self._messages.append(Prompt(role="system", content=system_prompt))

        self._last_message_timestamp: datetime | None = None
        self._token_counters = TokenCounters()

        # Загружаем память из репозитория при инициализации
        self.refresh_memory()

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

    def get_settings(self) -> AgentSettings:
        """Возвращает текущие настройки агента."""
        return self._settings

    def update_settings(self, new_settings: AgentSettings) -> None:
        """Обновляет настройки агента."""
        self._settings = new_settings
        if self._repository is not None and self._auto_save:
            self.save()

    def get_history(self) -> list[Prompt]:
        """Возвращает всю историю диалога (включая системный промпт)."""
        return self._messages.copy()

    def save(self) -> None:
        """
        Сохраняет текущее состояние агента.

        Если агент зарегистрирован в репозитории и включен auto_save,
        сохраняет метаданные и историю через репозиторий.
        """
        if self._repository is not None and self._auto_save:
            self._repository.update_agent(self)

    def continue_dialog(self, user_prompt: str) -> LlmResponse:
        """
        Продолжает диалог: добавляет сообщение пользователя, делает запрос к LLM,
        сохраняет ответ и возвращает результат.
        Args:
            user_prompt: Текст сообщения от пользователя.
        Returns:
            LlmResponse: Ответ от LLM с контентом и reasoning.
        Raises:
            ContextWindowExceededError: Если prompt_tokens превысил размер контекстного окна.
        """
        # Добавляем сообщение пользователя
        user_timestamp = datetime.now().astimezone()
        user_message = Prompt(
            role="user",
            content=user_prompt,
            timestamp=user_timestamp,
        )
        self._messages.append(user_message)
        self._last_message_timestamp = user_timestamp

        # Подготавливаем сообщения через стратегию
        memory_text = self.get_system_prompt_with_memory(None)

        # Проверяем наличие ЛЮБЫХ данных памяти или предпочтений,
        # чтобы не игнорировать профиль задачи, если глобальная память пуста
        has_memory_data = (
            bool(self.global_memory.facts)
            or (self.task_profile and bool(self.task_profile.facts))
            or (self.task_profile and bool(self.task_profile.preferences))
        )

        prepared = self._strategy.prepare_messages(
            history=self._messages,
            llm_provider=self._llm_provider,
            agent_memory_text=memory_text if has_memory_data else None,
        )

        messages_for_llm = prepared.messages
        settings = self._settings
        kwargs = settings.to_llm_request_properties()

        # Делаем запрос к LLM
        response = self._llm_provider.generate(messages=messages_for_llm, **kwargs)

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

        # Затем обновляем счетчики от основного запроса
        is_tech_request = prepared.is_summarization_request
        if response.prompt_tokens is not None:
            if is_tech_request:
                self._token_counters.tech_prompt_tokens += response.prompt_tokens
            else:
                self._token_counters.chat_prompt_tokens += response.prompt_tokens

        if response.completion_tokens is not None:
            if is_tech_request:
                self._token_counters.tech_completion_tokens += (
                    response.completion_tokens
                )
            else:
                self._token_counters.chat_completion_tokens += (
                    response.completion_tokens
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

        # Автосохранение после каждого сообщения
        if self._auto_save:
            self.save()

        return response

    @property
    def last_message_timestamp(self) -> datetime | None:
        """Возвращает временную метку последнего сообщения."""
        return self._last_message_timestamp

    @property
    def message_count(self) -> int:
        """Возвращает количество сообщений (без системного промпта)."""
        return len([msg for msg in self._messages if msg.role != "system"])

    def get_last_message_preview(self, max_length: int = 50) -> str | None:
        """Возвращает превью последнего сообщения пользователя или агента."""
        non_system_messages = [msg for msg in self._messages if msg.role != "system"]
        if not non_system_messages:
            return None

        last_msg = non_system_messages[-1]
        preview = last_msg.content[:max_length]
        if len(last_msg.content) > max_length:
            preview += "..."
        return preview

    def branch(
        self,
        new_name: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента-ветку на основе текущего.

        Копируются настройки, вся история сообщений, счетчики токенов и стратегия.
        Ветка получает новый conversation_id (UUID) для отдельного хранения истории.

        Args:
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """
        from datetime import datetime
        from uuid import uuid4

        from context_strategies import create_strategy_from_dict

        # Новый агент создается без ID - он будет установлен при сохранении в репозиторий
        if not new_name:
            timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            new_name = f"{self.name} (branch {timestamp})"

        current_settings = self.get_settings()
        current_history = self.get_history()

        current_strategy = self.strategy
        strategy_dict = current_strategy.to_dict()
        new_strategy = create_strategy_from_dict(strategy_dict)

        branched_agent = Agent(
            agent_id=None,
            conversation_id=str(uuid4()),
            name=new_name,
            llm_provider=self._llm_provider,
            initial_settings=current_settings,
            system_prompt=None,
            history_storage=self._history_storage,
            messages=current_history.copy(),
            strategy=new_strategy,
            auto_save=True,
            global_memory_repository=self._global_memory_repository,
            task_profile=self.task_profile,
            task_profile_repository=self._task_profile_repository,
        )

        branched_agent._repository = self._repository

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

        if self._repository is not None:
            self._repository.update_agent(branched_agent)

        return branched_agent

    def refresh_memory(self) -> None:
        """
        Загружает общесистемную память из репозитория.

        Вызывается при инициализации агента и при входе в чат.
        Репозиторий должен быть установлен (иначе агент не будет создан).
        """
        self.global_memory = self._global_memory_repository.get_memory()

    def save_memory(self) -> None:
        """
        Сохраняет общесистемную память о пользователе и память задачи.

        Если is_dialog_remembered == False:
        1. Достает все промпты с is_remembered == False
        2. Отправляет их в ЛЛМ для получения новых фактов:
           - Для глобальной памяти: факты о личности пользователя
           - Для памяти задачи: факты, относящиеся к задаче (если агент привязан к профилю)
        3. Объединяет старые и новые факты
        4. Сохраняет через соответствующие репозитории
        5. Помечает все промпты и агент как remembered

        Расход токенов записывается в tech_prompt_tokens и tech_completion_tokens.
        """
        import json

        if self.is_dialog_remembered:
            return  # Нечего сохранять

        # Находим все непромпты с is_remembered == False (только user и assistant)
        unremembered_prompts = [
            msg for msg in self._messages
            if not msg.is_remembered and msg.role in ("user", "assistant")
        ]

        if not unremembered_prompts:
            return  # Нет новых данных для запоминания

        dialog_text = ""
        for msg in unremembered_prompts:
            role_ru = "Пользователь" if msg.role == "user" else "Ассистент"
            dialog_text += f"{role_ru}: {msg.content}\\n"

        # === Сохранение глобальной памяти (факты о пользователе) ===
        old_facts_text = ""
        if self.global_memory.facts:
            old_facts_text = "Текущие факты о пользователе:\\n" + "\\n".join(f"- {f}" for f in self.global_memory.facts)

        global_system_prompt = (
            "Ты ассистент для извлечения фактов о пользователе из диалога. "
            "Твоя задача — найти новую информацию о пользователе (предпочтения, факты биографии, интересы и т.д.) "
            "и вернуть её в формате JSON.\\n\\n"
            "Важные правила:\\n"
            "1. Возвращай ТОЛЬКО новые факты, которых нет в текущем списке.\\n"
            "2. Игнорируй противоречия — просто добавляй новые факты.\\n"
            "3. Факты должны быть краткими и конкретными.\\n"
            "4. Если новых фактов нет, верни пустой список.\\n\\n"
            f"{old_facts_text}\\n\\n"
            f"Диалог для анализа:\\n{dialog_text}\\n\\n"
            "Верни ответ в формате JSON со схемой: "
            '{"facts": ["факт 1", "факт 2", ...]}'
        )

        messages_for_llm = [
            {"role": "system", "content": global_system_prompt},
            {"role": "user", "content": "Извлеки факты о пользователе из диалога выше."}
        ]

        response = self._llm_provider.generate(
            messages=messages_for_llm,
            temperature=0.1,
            max_tokens=1000,
            response_format={"type": "json_object"}
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
        self._global_memory_repository.save_memory(self.global_memory)

        # === Сохранение памяти задачи (если агент привязан к профилю) ===
        if self.task_profile and self._task_profile_repository:
            task_old_facts_text = ""
            if self.task_profile.facts:
                task_old_facts_text = (
                    f"Текущие факты о задаче \"{self.task_profile.name}\":\\n"
                    + "\\n".join(f"- {f}" for f in self.task_profile.facts)
                )

            task_system_prompt = (
                f"Ты ассистент для извлечения фактов о задаче из диалога. "
                f"Задача: {self.task_profile.name}. Описание: {self.task_profile.description}.\\n"
                "Твоя задача — найти новую информацию, относящуюся к задаче (прогресс, решения, ограничения, требования, результаты) "
                "и вернуть её в формате JSON.\\n\\n"
                "Важные правила:\\n"
                "1. Возвращай ТОЛЬКО новые факты, которых нет в текущем списке.\\n"
                "2. Игнорируй противоречия — просто добавляй новые факты.\\n"
                "3. Факты должны быть краткими и конкретными.\\n"
                "4. Если новых фактов нет, верни пустой список.\\n"
                "5. Извлекай только факты, относящиеся к задаче, а не к пользователю.\\n\\n"
                f"{task_old_facts_text}\\n\\n"
                f"Диалог для анализа:\\n{dialog_text}\\n\\n"
                "Верни ответ в формате JSON со схемой: "
                '{"facts": ["факт 1", "факт 2", ...]}'
            )

            messages_for_task_llm = [
                {"role": "system", "content": task_system_prompt},
                {"role": "user", "content": "Извлеки факты о задаче из диалога выше."}
            ]

            task_response = self._llm_provider.generate(
                messages=messages_for_task_llm,
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            # Обновляем счетчики технических токенов
            if task_response.prompt_tokens is not None:
                self._token_counters.tech_prompt_tokens += task_response.prompt_tokens
            if task_response.completion_tokens is not None:
                self._token_counters.tech_completion_tokens += task_response.completion_tokens

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
            self._task_profile_repository.save_facts(self.task_profile.id, all_task_facts)

        # Помечаем все промпты как remembered
        for msg in self._messages:
            msg.is_remembered = True

        # Помечаем агента как remembered
        self.is_dialog_remembered = True

    def get_system_prompt_with_memory(self, base_system_prompt: str | None) -> str:
        """
        Формирует системный промпт с добавлением памяти о пользователе и памяти задачи.

        Args:
            base_system_prompt: Базовый системный промпт (если есть).

        Returns:
            Полный системный промпт с памятью (глобальной и задачи).
        """
        memory_text = ""

        # Глобальная память
        if self.global_memory.facts:
            facts_list = "\\n".join(f"- {fact}" for fact in self.global_memory.facts)
            memory_text = f"\\n\\nПамять о пользователе:\\n{facts_list}"

        # Память задачи
        if self.task_profile and self.task_profile.facts:
            task_facts_list = "\\n".join(f"- {fact}" for fact in self.task_profile.facts)
            memory_text += f"\\n\\nПамять задачи ({self.task_profile.name}):\\n{task_facts_list}"

        # Предпочтения задачи
        if self.task_profile and self.task_profile.preferences:
            memory_text += f"\\n\\nПредпочтения задачи ({self.task_profile.name}):\\n{self.task_profile.preferences}"

        if base_system_prompt:
            return f"{base_system_prompt}{memory_text}"
        else:
            return f"Ты полезный ассистент.{memory_text}" if memory_text else "Ты полезный ассистент."
