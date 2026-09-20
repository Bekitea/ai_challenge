from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import (
    Agent,
    AgentPreview,
    AgentSettings,
)
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    create_strategy_from_dict,
)
from llm_providers import LlmProvider
from storage.conversation_repository import ConversationRepository
from storage.orm_models import AgentORM


class AgentRepository(ABC):
    """Абстракция для хранения и управления агентами."""

    @abstractmethod
    def create_agent(
        self,
        name: str,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        strategy: ContextWindowStrategy | None = None,
        task_profile_id: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента с уникальным идентификатором.

        Args:
            name: Название агента.
            llm_provider: Провайдер LLM для запросов.
            initial_settings: Начальные настройки агента.
            system_prompt: Системный промпт (опционально).
            strategy: Стратегия управления контекстным окном (опционально).
            task_profile_id: UUID профиля задачи (опционально).

        Returns:
            Agent: Newly created agent instance.
        """

    @abstractmethod
    def get_agent(self, agent_id: int) -> Agent | None:
        """
        Получает агента по идентификатору.

        Args:
            agent_id: Уникальный числовой идентификатор агента.

        Returns:
            Agent или None, если агент не найден.
        """

    @abstractmethod
    def get_all_previews(self) -> list[AgentPreview]:
        """
        Получает превью всех агентов, отсортированные по дате последнего сообщения
        (последние сверху).

        Returns:
            Список AgentPreview, отсортированный по last_message_timestamp (descending).
        """

    @abstractmethod
    def update_agent(self, agent: Agent) -> None:
        """
        Обновляет метаданные и историю агента.
        Вызывается после каждого изменения состояния агента.

        Args:
            agent: Агент для обновления.
        """

    @abstractmethod
    def delete_agent(self, agent_id: int) -> bool:
        """
        Удаляет агента из БД и удаляет файл истории.

        Args:
            agent_id: Числовой ID агента.

        Returns:
            True, если агент был удалён, False если не найден.
        """

    @abstractmethod
    def get_agents_with_unsaved_memory(self) -> list[Agent]:
        """
        Получает всех агентов с несохранённой памятью.
        Агент считается имеющим несохранённую память, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False

        Returns:
            Список агентов с несохранённой памятью.
        """


class PersistentAgentRepository(AgentRepository):
    """
    Реализация AgentRepository с хранением метаданных в SQLite и истории в файлах.

    Метаданные (настройки, превью, системный промпт) хранятся в БД.
    Полная история сообщений (Prompt objects) хранится в pickle-файлах.
    """

    def __init__(
        self,
        llm_provider: LlmProvider,
        session_factory: Callable[[], Session],
        global_memory_repository=None,
        task_profile_repository=None,
    ):
        """
        Инициализирует репозиторий.

        Args:
            llm_provider: Провайдер LLM для запросов.
            session_factory: Фабрика сессий БД. Внешняя зависимость,
                            предоставляемая слоем инфраструктуры.
            global_memory_repository: Репозиторий глобальной памяти (опционально).
            task_profile_repository: Репозиторий профилей задач (опционально).
        """
        self._session_factory = session_factory
        self._llm_provider = llm_provider
        self._chat_storage = ConversationRepository()
        self._global_memory_repository = global_memory_repository
        self._task_profile_repository = task_profile_repository

    def _get_session(self) -> Session:
        """Возвращает новую сессию БД."""
        return self._session_factory()

    def _agent_orm_to_agent(self, orm: AgentORM) -> Agent:
        """
        Преобразует ORM объект в Agent, загружая историю из файла.

        Args:
            orm: ORM объект агента.

        Returns:
            Agent: Экземпляр агента с загруженной историей.
        """
        settings = orm.get_settings()

        # Загружаем стратегию
        strategy_type = orm.strategy_type or "DefaultStrategy"
        strategy_params = orm.get_strategy_params()
        if strategy_params:
            strategy_data = {"strategy_type": strategy_type, **strategy_params}
            strategy = create_strategy_from_dict(strategy_data)
        else:
            strategy = DefaultStrategy()

        # Загружаем историю из файла по conversation_id (UUID)
        history = self._chat_storage.load_history(orm.conversation_id)

        # Загружаем профиль задачи, если он привязан
        task_profile = None
        if orm.task_profile_id is not None and self._task_profile_repository is not None:
            task_profile = self._task_profile_repository.get_profile_by_id(orm.task_profile_id)

        agent = Agent(
            agent_id=orm.id,
            conversation_id=orm.conversation_id,
            name=orm.name,
            llm_provider=self._llm_provider,
            initial_settings=settings,
            system_prompt=orm.system_prompt,
            history_storage=self._chat_storage,
            messages=history if history else None,
            strategy=strategy,
            auto_save=True,
            global_memory_repository=self._global_memory_repository,
            task_profile=task_profile,                              # ✅ ДОБАВЛЕНО
            task_profile_repository=self._task_profile_repository,  # ✅ ДОБАВЛЕНО
        )

        # Устанавливаем ссылку на репозиторий для автосохранения
        agent._repository = self

        # Восстанавливаем счетчики токенов
        agent._token_counters.chat_prompt_tokens = orm.chat_prompt_tokens
        agent._token_counters.chat_completion_tokens = orm.chat_completion_tokens
        agent._token_counters.tech_prompt_tokens = orm.tech_prompt_tokens
        agent._token_counters.tech_completion_tokens = orm.tech_completion_tokens

        # Восстанавливаем is_dialog_remembered из БД
        agent.is_dialog_remembered = orm.is_dialog_remembered

        # Восстанавливаем last_message_timestamp из истории
        if history:
            non_system_msgs = [m for m in history if m.role != "system"]
            if non_system_msgs:
                agent._last_message_timestamp = non_system_msgs[-1].timestamp

        return agent

    def _save_agent_metadata(self, agent: Agent) -> None:
        """
        Сохраняет метаданные агента в БД.

        Args:
            agent: Агент для сохранения.
        """
        with self._get_session() as session:
            orm = session.get(AgentORM, agent.agent_id)
            if orm is None:
                orm = AgentORM()
                session.add(orm)

            orm.name = agent.name
            orm.last_message_timestamp = agent.last_message_timestamp
            orm.message_count = agent.message_count
            orm.last_message_preview = agent.get_last_message_preview()
            orm.set_settings(agent.get_settings())

            # Сохраняем conversation_id, если он установлен (например, при ветвлении)
            if agent.conversation_id:
                orm.conversation_id = agent.conversation_id

            # Сохраняем системный промпт, если он есть
            history = agent.get_history()
            system_msgs = [m for m in history if m.role == "system"]
            if system_msgs:
                orm.system_prompt = system_msgs[0].content

            # Сохраняем стратегию
            strategy = agent.strategy
            orm.strategy_type = strategy.strategy_type
            strategy_dict = strategy.to_dict()
            # Удаляем strategy_type из параметров, так как он хранится отдельно
            params = {k: v for k, v in strategy_dict.items() if k != "strategy_type"}
            orm.set_strategy_params(params if params else None)

            # Сохраняем счетчики токенов
            counters = agent.token_counters
            orm.chat_prompt_tokens = counters.chat_prompt_tokens
            orm.chat_completion_tokens = counters.chat_completion_tokens
            orm.tech_prompt_tokens = counters.tech_prompt_tokens
            orm.tech_completion_tokens = counters.tech_completion_tokens

            # Сохраняем is_dialog_remembered
            orm.is_dialog_remembered = agent.is_dialog_remembered

            session.commit()

            # После commit получаем сгенерированный ID и conversation_id, если это новый агент
            if agent.agent_id is None:
                agent.agent_id = orm.id

    def _save_agent_history(self, agent: Agent) -> None:
        """
        Сохраняет историю сообщений агента в файл.

        Args:
            agent: Агент для сохранения.
        """
        conversation_id = agent.conversation_id
        history = agent.get_history()
        self._chat_storage.save_history(conversation_id, history)

    def create_agent(
        self,
        name: str,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        strategy: ContextWindowStrategy | None = None,
        task_profile_id: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента и сохраняет в БД и файл.

        Args:
            name: Название агента.
            llm_provider: Провайдер LLM.
            initial_settings: Начальные настройки.
            system_prompt: Системный промпт.
            strategy: Стратегия управления контекстным окном (по умолчанию DefaultStrategy).
            task_profile_id: UUID профиля задачи (опционально).

        Returns:
            Agent: Новый экземпляр агента.
        """
        # Создаем агента с conversation_id - он будет установлен после сохранения ORM
        from uuid import uuid4

        temp_conversation_id = str(uuid4())  # Временный ID до сохранения в БД

        # Загружаем профиль задачи, если указан
        task_profile = None
        if task_profile_id is not None and self._task_profile_repository is not None:
            task_profile = self._task_profile_repository.get_profile_by_id(task_profile_id)

        agent = Agent(
            agent_id=None,  # Будет установлен после сохранения в БД
            conversation_id=temp_conversation_id,  # Временный ID, заменится после commit
            name=name,
            llm_provider=self._llm_provider,
            initial_settings=initial_settings,
            system_prompt=system_prompt,
            strategy=strategy,
            auto_save=True,  # Включаем автосохранение для новых агентов
            global_memory_repository=self._global_memory_repository,
            task_profile=task_profile,                              # ✅ ДОБАВЛЕНО
            task_profile_repository=self._task_profile_repository,  # ✅ ДОБАВЛЕНО
        )

        # Устанавливаем ссылку на репозиторий для автосохранения
        agent._repository = self

        # Сохраняем метаданные в БД и получаем сгенерированные ID
        with self._get_session() as session:
            orm = AgentORM()
            orm.name = name
            orm.set_settings(initial_settings)
            orm.system_prompt = system_prompt
            orm.last_message_timestamp = None
            orm.message_count = 0
            orm.last_message_preview = None

            # Сохраняем стратегию
            if strategy:
                orm.strategy_type = strategy.strategy_type
                strategy_dict = strategy.to_dict()
                params = {
                    k: v for k, v in strategy_dict.items() if k != "strategy_type"
                }
                orm.set_strategy_params(params if params else None)
            else:
                orm.strategy_type = "DefaultStrategy"
                orm.set_strategy_params(None)

            # Инициализируем счетчики нулями
            orm.chat_prompt_tokens = 0
            orm.chat_completion_tokens = 0
            orm.tech_prompt_tokens = 0
            orm.tech_completion_tokens = 0

            # Привязываем профиль задачи, если указан
            if task_profile_id is not None:
                orm.task_profile_id = task_profile_id

            session.add(orm)
            session.commit()

            # После commit ORM получает сгенерированный числовой id и conversation_id
            agent.agent_id = orm.id
            agent.conversation_id = orm.conversation_id

        # Сохраняем начальную историю (системный промпт) в файл по conversation_id
        self._chat_storage.save_history(agent.conversation_id, agent.get_history())

        return agent

    def get_agent(self, agent_id: int) -> Agent | None:
        """
        Получает агента по числовому ID, загружая историю из файла.

        Args:
            agent_id: Числовой ID агента.

        Returns:
            Agent или None, если не найден.
        """
        with self._get_session() as session:
            orm = session.get(AgentORM, agent_id)
            if orm is None:
                return None
            return self._agent_orm_to_agent(orm)

    def get_all_previews(self) -> list[AgentPreview]:
        """
        Получает превью всех агентов из БД, отсортированные по дате последнего сообщения.

        Returns:
            Список AgentPreview, отсортированный по last_message_timestamp (descending).
        """
        with self._get_session() as session:
            # SQLite не поддерживает NULLS FIRST с DESC, поэтому загружаем все и сортируем в Python
            stmt = select(AgentORM)
            orms = session.execute(stmt).scalars().all()

            previews = []
            for orm in orms:
                preview = AgentPreview(
                    agent_id=orm.id,  # Числовой ID для отображения пользователю
                    name=orm.name,
                    last_message_timestamp=orm.last_message_timestamp,
                    message_count=orm.message_count,
                    last_message_preview=orm.last_message_preview,
                )
                previews.append(preview)

            # Сортировка: None в конце, остальные по убыванию
            previews.sort(
                key=lambda p: (
                    p.last_message_timestamp
                    if p.last_message_timestamp
                    else datetime.min
                ),
                reverse=True,
            )
            return previews

    def update_agent(self, agent: Agent) -> None:
        """
        Обновляет метаданные и историю агента.
        Вызывается после каждого изменения состояния агента.

        Args:
            agent: Агент для обновления.
        """
        self._save_agent_metadata(agent)
        self._save_agent_history(agent)

    def delete_agent(self, agent_id: int) -> bool:
        """
        Удаляет агента из БД и удаляет файл истории.

        Args:
            agent_id: Числовой ID агента.

        Returns:
            True, если агент был удалён, False если не найден.
        """
        with self._get_session() as session:
            orm = session.get(AgentORM, agent_id)
            if orm is None:
                return False

            # Получаем conversation_id перед удалением записи из БД
            conversation_id = orm.conversation_id

            session.delete(orm)
            session.commit()

        # Удаляем файл истории по conversation_id
        self._chat_storage.delete_history(conversation_id)
        return True

    def get_agents_with_unsaved_memory(self) -> list[Agent]:
        """
        Получает всех агентов с несохранённой памятью.
        Агент считается имеющим несохранённую память, если:
        - is_dialog_remembered == False
        - Есть сообщения с is_remembered == False

        Сначала делаем SQL запрос для получения агентов с is_dialog_remembered == False,
        затем загружаем их историю из файлового хранилища и фильтруем тех,
        у кого есть сообщения с is_remembered == False.

        Returns:
            Список агентов с несохранённой памятью.
        """
        with self._get_session() as session:
            # Получаем всех агентов с is_dialog_remembered == False
            stmt = select(AgentORM).where(AgentORM.is_dialog_remembered == False)
            orms = session.execute(stmt).scalars().all()

            # Загружаем агентов и проверяем их историю из файлового хранилища
            agents_with_unsaved = []
            for orm in orms:
                agent = self._agent_orm_to_agent(orm)
                # Проверяем, есть ли непромптированные сообщения
                unremembered_prompts = [
                    msg for msg in agent.get_history()
                    if not msg.is_remembered and msg.role in ("user", "assistant")
                ]
                if unremembered_prompts:
                    agents_with_unsaved.append(agent)

            return agents_with_unsaved
