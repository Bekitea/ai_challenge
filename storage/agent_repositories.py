from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from agents import (
    Agent,
    AgentPreview,
    AgentSettings,
)
from config import DATABASE_URL
from context_strategies import (
    ContextWindowStrategy,
    DefaultStrategy,
    create_strategy_from_dict,
)
from llm_providers import LlmProvider
from storage.chat_storage import ChatHistoryStorage
from storage.orm_models import AgentORM, Base


class AgentRepository(ABC):
    """Абстракция для хранения и управления агентами."""

    @abstractmethod
    def create_agent(
        self,
        name: str,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента с уникальным идентификатором.

        Args:
            name: Название агента.
            llm_provider: Провайдер LLM для запросов.
            initial_settings: Начальные настройки агента.
            system_prompt: Системный промпт (опционально).

        Returns:
            Agent: Newly created agent instance.
        """

    @abstractmethod
    def get_agent(self, agent_id: str) -> Agent | None:
        """
        Получает агента по идентификатору.

        Args:
            agent_id: Уникальный идентификатор агента.

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
    def delete_agent(self, agent_id: str) -> bool:
        """
        Удаляет агента из БД и удаляет файл истории.

        Args:
            agent_id: UUID агента.

        Returns:
            True, если агент был удалён, False если не найден.
        """

    @abstractmethod
    def branch_agent(
        self,
        parent_agent: Agent,
        new_name: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента-ветку на основе существующего.

        Копируются настройки, вся история сообщений и саммари (если есть).

        Args:
            parent_agent: Родительский агент.
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """


class PersistentAgentRepository(AgentRepository):
    """
    Реализация AgentRepository с хранением метаданных в SQLite и истории в файлах.

    Метаданные (настройки, превью, системный промпт) хранятся в БД.
    Полная история сообщений (Prompt objects) хранится в pickle-файлах.
    """

    def __init__(self, llm_provider: LlmProvider):
        """
        Инициализирует репозиторий.

        Args:
            llm_provider_factory: Фабрика для создания LLM провайдера.
                                  Вызывается при загрузке каждого агента.
        """
        self._engine = create_engine(DATABASE_URL, echo=False)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False)
        self._llm_provider = llm_provider
        self._chat_storage = ChatHistoryStorage()

    def init_db(self) -> None:
        """Создаёт таблицы в БД, если они не существуют."""
        Base.metadata.create_all(bind=self._engine)

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

        # Загружаем историю из файла
        history = self._chat_storage.load_history(orm.id)

        agent = Agent(
            agent_id=orm.id,
            name=orm.name,
            llm_provider=self._llm_provider,
            initial_settings=settings,
            system_prompt=orm.system_prompt,
            history_storage=self._chat_storage,
            messages=history if history else None,
            strategy=strategy,
        )

        # Восстанавливаем счетчики токенов
        agent._token_counters.chat_prompt_tokens = orm.chat_prompt_tokens
        agent._token_counters.chat_completion_tokens = orm.chat_completion_tokens
        agent._token_counters.tech_prompt_tokens = orm.tech_prompt_tokens
        agent._token_counters.tech_completion_tokens = orm.tech_completion_tokens

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
                orm.id = agent.agent_id
                session.add(orm)

            orm.name = agent.name
            orm.last_message_timestamp = agent.last_message_timestamp
            orm.message_count = agent.message_count
            orm.last_message_preview = agent.get_last_message_preview()
            orm.set_settings(agent.get_settings())

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

            session.commit()

    def _save_agent_history(self, agent: Agent) -> None:
        """
        Сохраняет историю сообщений агента в файл.

        Args:
            agent: Агент для сохранения.
        """
        history = agent.get_history()
        self._chat_storage.save_history(agent.agent_id, history)

    def create_agent(
        self,
        name: str,
        initial_settings: AgentSettings | None = None,
        system_prompt: str | None = None,
        strategy: ContextWindowStrategy | None = None,
    ) -> Agent:
        """
        Создаёт нового агента и сохраняет в БД и файл.

        Args:
            name: Название агента.
            llm_provider: Провайдер LLM.
            initial_settings: Начальные настройки.
            system_prompt: Системный промпт.
            strategy: Стратегия управления контекстным окном (по умолчанию DefaultStrategy).

        Returns:
            Agent: Новый экземпляр агента.
        """
        from uuid import uuid4

        agent_id = str(uuid4())
        agent = Agent(
            agent_id=agent_id,
            name=name,
            llm_provider=self._llm_provider,
            initial_settings=initial_settings,
            system_prompt=system_prompt,
            strategy=strategy,
        )

        # Сохраняем метаданные в БД
        with self._get_session() as session:
            orm = AgentORM()
            orm.id = agent_id
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
                params = {k: v for k, v in strategy_dict.items() if k != "strategy_type"}
                orm.set_strategy_params(params if params else None)
            else:
                orm.strategy_type = "DefaultStrategy"
                orm.set_strategy_params(None)

            # Инициализируем счетчики нулями
            orm.chat_prompt_tokens = 0
            orm.chat_completion_tokens = 0
            orm.tech_prompt_tokens = 0
            orm.tech_completion_tokens = 0

            session.add(orm)
            session.commit()

        # Сохраняем начальную историю (системный промпт) в файл
        self._save_agent_history(agent)

        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """
        Получает агента по ID, загружая историю из файла.

        Args:
            agent_id: UUID агента.

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
                    agent_id=orm.id,
                    name=orm.name,
                    last_message_timestamp=orm.last_message_timestamp,
                    message_count=orm.message_count,
                    last_message_preview=orm.last_message_preview,
                )
                previews.append(preview)

            # Сортировка: None в конце, остальные по убыванию
            previews.sort(
                key=lambda p: p.last_message_timestamp if p.last_message_timestamp else datetime.min,
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

    def delete_agent(self, agent_id: str) -> bool:
        """
        Удаляет агента из БД и удаляет файл истории.

        Args:
            agent_id: UUID агента.

        Returns:
            True, если агент был удалён, False если не найден.
        """
        with self._get_session() as session:
            orm = session.get(AgentORM, agent_id)
            if orm is None:
                return False

            session.delete(orm)
            session.commit()

        # Удаляем файл истории
        self._chat_storage.delete_history(agent_id)
        return True

    def branch_agent(
        self,
        parent_agent: Agent,
        new_name: str | None = None,
    ) -> Agent:
        """
        Создаёт нового агента-ветку на основе существующего.

        Копируются настройки, вся история сообщений и саммари (если есть).

        Args:
            parent_agent: Родительский агент.
            new_name: Новое название для ветки (опционально).

        Returns:
            Agent: Новый агент-ветка.
        """
        from uuid import uuid4

        # Генерируем новый ID
        new_agent_id = str(uuid4())

        # Генерируем имя если не указано
        if not new_name:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_name = f"{parent_agent.name} (branch {timestamp})"

        # Получаем настройки и историю родительского агента
        parent_settings = parent_agent.get_settings()
        parent_history = parent_agent.get_history()

        # Получаем стратегию и копируем её
        parent_strategy = parent_agent.strategy
        strategy_dict = parent_strategy.to_dict()
        new_strategy = create_strategy_from_dict(strategy_dict)

        # Создаём нового агента
        agent = Agent(
            agent_id=new_agent_id,
            name=new_name,
            llm_provider=self._llm_provider,
            initial_settings=parent_settings,
            system_prompt=None,  # Системный промпт уже есть в истории
            history_storage=self._chat_storage,
            messages=parent_history.copy(),  # Копируем всю историю
            strategy=new_strategy,
        )

        # Восстанавливаем счетчики токенов
        parent_counters = parent_agent.token_counters
        agent._token_counters.chat_prompt_tokens = parent_counters.chat_prompt_tokens
        agent._token_counters.chat_completion_tokens = parent_counters.chat_completion_tokens
        agent._token_counters.tech_prompt_tokens = parent_counters.tech_prompt_tokens
        agent._token_counters.tech_completion_tokens = parent_counters.tech_completion_tokens

        # Восстанавливаем last_message_timestamp
        if parent_history:
            non_system_msgs = [m for m in parent_history if m.role != "system"]
            if non_system_msgs:
                agent._last_message_timestamp = non_system_msgs[-1].timestamp

        # Сохраняем метаданные в БД
        with self._get_session() as session:
            orm = AgentORM()
            orm.id = new_agent_id
            orm.name = new_name
            orm.set_settings(parent_settings)

            # Системный промпт берём из истории
            system_msgs = [m for m in parent_history if m.role == "system"]
            if system_msgs:
                orm.system_prompt = system_msgs[0].content

            orm.last_message_timestamp = agent.last_message_timestamp
            orm.message_count = agent.message_count
            orm.last_message_preview = agent.get_last_message_preview()

            # Сохраняем стратегию
            orm.strategy_type = new_strategy.strategy_type
            strategy_params_dict = new_strategy.to_dict()
            params = {k: v for k, v in strategy_params_dict.items() if k != "strategy_type"}
            orm.set_strategy_params(params if params else None)

            # Сохраняем счетчики токенов
            counters = agent.token_counters
            orm.chat_prompt_tokens = counters.chat_prompt_tokens
            orm.chat_completion_tokens = counters.chat_completion_tokens
            orm.tech_prompt_tokens = counters.tech_prompt_tokens
            orm.tech_completion_tokens = counters.tech_completion_tokens

            session.add(orm)
            session.commit()

        # Сохраняем историю в файл
        self._save_agent_history(agent)

        return agent
