from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agents import (
    Agent,
    AgentPreview,
    AgentSettings,
    Prompt,
    TaskProfile,
)
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    KeyValueMemoryStrategy,
    SlidingWindowStrategy,
    SummarizationStrategy,
)
from llm_providers import LlmProvider, LlmResponse
from storage.agent_repositories import AgentRepository


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


@dataclass
class ChatInfo:
    """Информация о чате для отображения."""

    name: str
    agent_id: int
    strategy_type: str
    message_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    has_summary: bool = False
    non_compressible_count: int | None = None
    buffer_size: int | None = None


@dataclass
class StrategySelection:
    """Выбранная стратегия с параметрами."""

    strategy_type: str
    non_compressible_count: int | None = None
    buffer_size: int | None = None
    window_size: int | None = None


class CreateChatUseCase:
    """Use case для создания нового чата."""

    def __init__(self, repository: AgentRepository, llm_provider: LlmProvider, task_profile_repository=None):
        self.repository = repository
        self.llm_provider = llm_provider
        self.task_profile_repository = task_profile_repository

    def execute(
        self,
        name: str,
        system_prompt: str | None,
        settings: AgentSettings,
        strategy: ContextWindowStrategy,
        task_profile_id: str | None = None,
    ) -> Agent:
        """
        Создаёт новый чат с указанными настройками.

        Args:
            name: Название чата.
            system_prompt: Системный промпт (опционально).
            settings: Настройки агента.
            strategy: Стратегия управления контекстным окном.
            task_profile_id: UUID профиля задачи (опционально).

        Returns:
            Agent: Созданный агент.

        Raises:
            ValueError: Если указан несуществующий профиль задачи.
        """
        # Проверка существования профиля задачи, если он указан
        if task_profile_id is not None and self.task_profile_repository is not None:
            profile = self.task_profile_repository.get_profile_by_id(task_profile_id)
            if profile is None:
                raise ValueError(f"Профиль задачи с ID {task_profile_id} не найден")

        agent = self.repository.create_agent(
            name=name,
            initial_settings=settings,
            system_prompt=system_prompt,
            strategy=strategy,
            task_profile_id=task_profile_id,
        )
        return agent


class SelectChatUseCase:
    """Use case для выбора существующего чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def get_all_previews(self) -> list[AgentPreview]:
        """Получает список всех чатов."""
        return self.repository.get_all_previews()

    def get_agent(self, agent_id: int) -> Agent | None:
        """Получает агент по числовому ID."""
        return self.repository.get_agent(agent_id)


class SendMessageUseCase:
    """Use case для отправки сообщения и получения ответа."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent: Agent, user_message: str) -> tuple[LlmResponse, Agent]:
        """
        Отправляет сообщение агенту и получает ответ.

        Args:
            agent: Агент для общения.
            user_message: Текст сообщения пользователя.

        Returns:
            Tuple of (LlmResponse, updated Agent).

        Raises:
            ContextWindowExceededError: Если превышен лимит контекстного окна.
        """
        response = agent.continue_dialog(user_message)
        return response, agent


class ViewSettingsUseCase:
    """Use case для просмотра настроек чата."""

    def execute(self, agent: Agent | None) -> AgentSettings | None:
        """Получает настройки текущего агента."""
        if not agent:
            return None
        return agent.get_settings()


class ChangeSettingsUseCase:
    """Use case для изменения настроек чата."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self, agent: Agent, new_settings: AgentSettings) -> None:
        """
        Обновляет настройки агента.

        Args:
            agent: Агент для обновления.
            new_settings: Новые настройки.
        """
        agent.update_settings(new_settings)


class ShowHistoryUseCase:
    """Use case для показа истории чата."""

    def execute(self, agent: Agent | None) -> list[Prompt] | None:
        """Получает историю сообщений агента."""
        if not agent:
            return None
        return agent.get_history()


class ShowSummaryUseCase:
    """Use case для показа саммари диалога."""

    def execute(self, agent: Agent | None) -> str | None:
        """
        Получает саммари из стратегии агента.

        Args:
            agent: Агент для получения саммари.

        Returns:
            Саммари или None, если оно отсутствует.
        """
        if not agent:
            return None

        strategy = agent.strategy
        if hasattr(strategy, "summary"):
            return strategy.summary
        return None


class ShowChatInfoUseCase:
    """Use case для показа информации о чате."""

    def execute(self, agent: Agent | None) -> ChatInfo | None:
        """
        Получает информацию о чате включая счетчики токенов.

        Args:
            agent: Агент для получения информации.

        Returns:
            ChatInfo или None, если агент не выбран.
        """
        if not agent:
            return None

        counters = agent.token_counters
        strategy = agent.strategy

        has_summary = False
        non_compressible_count = None
        buffer_size = None

        if hasattr(strategy, "summary") and strategy.summary:
            has_summary = True
        if hasattr(strategy, "non_compressible_count"):
            non_compressible_count = strategy.non_compressible_count
        if hasattr(strategy, "buffer_size"):
            buffer_size = strategy.buffer_size

        return ChatInfo(
            name=agent.name,
            agent_id=agent.agent_id,
            strategy_type=strategy.strategy_type,
            message_count=agent.message_count,
            total_prompt_tokens=counters.total_prompt_tokens,
            total_completion_tokens=counters.total_completion_tokens,
            has_summary=has_summary,
            non_compressible_count=non_compressible_count,
            buffer_size=buffer_size,
        )


class CreateBranchUseCase:
    """Use case для создания ветки текущего чата."""

    def execute(self, parent_agent: Agent, new_name: str | None = None) -> Agent:
        """
        Создаёт ветку текущего чата.

        Args:
            parent_agent: Родительский агент.
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """
        return parent_agent.branch(new_name=new_name)


class SelectContextStrategyUseCase:
    """Use case для выбора стратегии управления контекстным окном."""

    def execute(self, selection: StrategySelection) -> ContextWindowStrategy:
        """
        Создаёт стратегию на основе выбора пользователя.

        Args:
            selection: Выбранная стратегия с параметрами.

        Returns:
            ContextWindowStrategy: Экземпляр стратегии.
        """
        if selection.strategy_type == "DefaultStrategy":
            return DefaultStrategy()

        elif selection.strategy_type == "SummarizationStrategy":
            return SummarizationStrategy(
                non_compressible_count=selection.non_compressible_count or 2,
                buffer_size=selection.buffer_size or 3,
            )

        elif selection.strategy_type == "KeyValueMemoryStrategy":
            return KeyValueMemoryStrategy(
                non_compressible_count=selection.non_compressible_count or 2,
                buffer_size=selection.buffer_size or 3,
            )

        elif selection.strategy_type == "SlidingWindowStrategy":
            return SlidingWindowStrategy(
                window_size=selection.window_size or 10,
            )

        else:
            return DefaultStrategy()


class ViewGlobalMemoryUseCase:
    """Use case для просмотра глобальной памяти агента."""

    def __init__(self, memory_repository):
        self.memory_repository = memory_repository

    def execute(self) -> list[str]:
        """
        Получает список фактов из глобальной памяти.

        Returns:
            Список фактов.
        """
        memory = self.memory_repository.get_memory()
        return memory.facts


class RefreshAgentMemoryUseCase:
    """Use case для загрузки памяти агента при выборе чата."""

    def __init__(self, global_memory_repository):
        self.global_memory_repository = global_memory_repository

    def execute(self, agent: Agent) -> None:
        """
        Загружает общесистемную память из репозитория.

        Args:
            agent: Агент, для которого нужно загрузить память.
        """
        agent.refresh_memory()


class SaveAgentMemoryUseCase:
    """Use case для сохранения памяти агента при выходе из чата."""

    def __init__(self, global_memory_repository):
        self.global_memory_repository = global_memory_repository

    def execute(self, agent: Agent) -> None:
        """
        Сохраняет общесистемную память о пользователе.

        Args:
            agent: Агент, для которого нужно сохранить память.
        """
        agent.save_memory()


class SaveUnsavedMemoriesUseCase:
    """Use case для сохранения всех несохранённых памятей при старте приложения."""

    def __init__(self, repository: AgentRepository):
        self.repository = repository

    def execute(self) -> None:
        """
        Находит все агенты с несохранёнными промптами и вызывает у них save_memory.

        Агент считается имеющим несохранённые промпты, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False
        """
        agents = self.repository.get_agents_with_unsaved_memory()

        for agent in agents:
            agent.save_memory()


@dataclass
class TaskProfileInfo:
    """Информация о профиле задачи для отображения."""
    id: str
    name: str
    description: str
    created_at: datetime | None
    facts_count: int


class ListTaskProfilesUseCase:
    """Use case для просмотра списка профилей задач."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self) -> list[TaskProfileInfo]:
        """
        Получает список всех профилей задач.

        Returns:
            Список TaskProfileInfo.
        """
        profiles = self.task_profile_repository.get_all_profiles()
        return [
            TaskProfileInfo(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                facts_count=len(p.facts),
            )
            for p in profiles
        ]


class CreateTaskProfileUseCase:
    """Use case для создания нового профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, name: str, description: str) -> TaskProfile:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.

        Returns:
            TaskProfile: Созданный профиль.
        """
        return self.task_profile_repository.create_profile(name, description)


class GetTaskProfileMemoryUseCase:
    """Use case для просмотра памяти выбранного профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> TaskProfile | None:
        """
        Получает информацию о профиле задачи и его память.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            TaskProfile или None, если профиль не найден.
        """
        return self.task_profile_repository.get_profile_by_id(profile_id)


class DeleteTaskProfileUseCase:
    """Use case для удаления профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> bool:
        """
        Удаляет профиль задачи.

        Args:
            profile_id: UUID профиля для удаления.

        Returns:
            True, если профиль был удалён, False если не найден или привязан к агентам.
        """
        # Проверяем, привязан ли профиль к агентам
        if self.task_profile_repository.is_profile_linked_to_agents(profile_id):
            return False

        return self.task_profile_repository.delete_profile(profile_id)
