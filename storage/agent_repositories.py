from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.domain.dtos.agent_preview import AgentPreview
from core.domain.dtos.agent_settings import AgentSettings
from core.domain.dtos.global_memory import GlobalMemory
from core.domain.dtos.prompt import Prompt
from core.domain.dtos.task_memory import TaskMemory
from core.domain.entities.agent import Agent
from core.domain.entities.agent_phase import AgentPhase
from core.domain.entities.context_strategy_factory import create_strategy_from_dict
from core.domain.entities.context_window_strategy import ContextWindowStrategy
from core.domain.entities.default_strategy import DefaultStrategy
from storage.conversation_repository import ConversationRepository
from storage.orm_models import AgentORM


class PersistentAgentRepository:
    """
    Репозиторий агентов: CRUD и персистентность памяти/истории.

    Метаданные (настройки, превью, системный промпт) хранятся в БД.
    Полная история сообщений (Prompt objects) хранится в pickle-файлах.
    Глобальная память, память задачи и факты профилей делегируются
    соответствующим хранилищам, которые репозиторий агрегирует как
    единая точка доступа к персистентности агента.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        conversation_storage: ConversationRepository | None = None,
        global_memory_repository=None,
        task_profile_repository=None,
        task_memory_repository=None,
    ):
        """
        Инициализирует репозиторий.

        Args:
            session_factory: Фабрика сессий БД. Внешняя зависимость,
                предоставляемая слоем инфраструктуры.
            conversation_storage: Хранилище истории сообщений.
            global_memory_repository: Хранилище глобальной памяти.
            task_profile_repository: Хранилище профилей задач.
            task_memory_repository: Хранилище памяти задачи диалога.
        """
        self._session_factory = session_factory
        self._chat_storage = conversation_storage or ConversationRepository()
        self._global_memory_repository = global_memory_repository
        self._task_profile_repository = task_profile_repository
        self._task_memory_repository = task_memory_repository

    def _get_session(self) -> Session:
        """Возвращает новую сессию БД."""
        return self._session_factory()

    # ------------------------------------------------------------------
    # Память и история (единая точка доступа для агента)
    # ------------------------------------------------------------------

    @staticmethod
    def _require(store, name: str):
        """Возвращает хранилище или падает, если оно не настроено.

        Репозиторий не бросает доменных исключений: это инфраструктурная
        ошибка конфигурации, которую агент при вызове метода оборачивает в
        доменное исключение доступа.
        """
        if store is None:
            raise RuntimeError(f"Хранилище '{name}' не настроено")
        return store

    def get_global_memory(self) -> GlobalMemory:
        """Загружает общесистемную память о пользователе."""
        store = self._require(
            self._global_memory_repository, "global_memory_repository"
        )
        return store.get_memory()

    def save_global_memory(self, memory: GlobalMemory) -> None:
        """Сохраняет общесистемную память о пользователе."""
        store = self._require(
            self._global_memory_repository, "global_memory_repository"
        )
        store.save_memory(memory)

    def get_task_memory(self, conversation_id: str) -> TaskMemory | None:
        """Загружает память задачи диалога или None, если её нет."""
        store = self._require(
            self._task_memory_repository, "task_memory_repository"
        )
        return store.get_memory(conversation_id)

    def save_task_memory(self, conversation_id: str, memory: TaskMemory) -> None:
        """Сохраняет память задачи диалога."""
        store = self._require(
            self._task_memory_repository, "task_memory_repository"
        )
        store.save_memory(conversation_id, memory)

    def delete_task_memory(self, conversation_id: str) -> None:
        """Удаляет память задачи диалога."""
        store = self._require(
            self._task_memory_repository, "task_memory_repository"
        )
        store.delete_memory(conversation_id)

    def save_task_profile_facts(self, profile_id: str, facts: list[str]) -> None:
        """Сохраняет факты профиля задачи."""
        store = self._require(
            self._task_profile_repository, "task_profile_repository"
        )
        store.save_facts(profile_id, facts)

    # ------------------------------------------------------------------
    # Гидратация / сохранение агента
    # ------------------------------------------------------------------

    def _agent_orm_to_agent(
        self,
        orm: AgentORM,
        *,
        history: list[Prompt] | None = None,
    ) -> Agent:
        """
        Преобразует ORM объект в Agent, загружая историю из файла.

        Args:
            orm: ORM объект агента.
            history: Заранее загруженная история (чтобы не читать файл дважды).

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
        if history is None:
            history = self._chat_storage.load_history(orm.conversation_id)

        # Загружаем профиль задачи, если он привязан
        task_profile = None
        if (
            orm.task_profile_id is not None
            and self._task_profile_repository is not None
        ):
            task_profile = self._task_profile_repository.get_profile_by_id(
                orm.task_profile_id
            )

        agent = Agent(
            agent_id=orm.id,
            conversation_id=orm.conversation_id,
            name=orm.name,
            initial_settings=settings,
            system_prompt=orm.system_prompt,
            messages=history if history else None,
            strategy=strategy,
            task_profile=task_profile,
            connected_mcp_servers=orm.get_mcp_servers(),
        )

        # Восстанавливаем счетчики токенов
        agent._token_counters.chat_prompt_tokens = orm.chat_prompt_tokens
        agent._token_counters.chat_completion_tokens = orm.chat_completion_tokens
        agent._token_counters.tech_prompt_tokens = orm.tech_prompt_tokens
        agent._token_counters.tech_completion_tokens = orm.tech_completion_tokens

        # Восстанавливаем is_dialog_remembered из БД
        agent.is_dialog_remembered = orm.is_dialog_remembered

        # Восстанавливаем счётчик ходов до обновления памяти задачи
        agent.turns_since_task_memory = orm.turns_since_task_memory

        # Восстанавливаем current_phase из БД
        phase = orm.get_current_phase()
        if phase is not None:
            agent._current_phase = phase

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
            orm = None
            if agent.agent_id is not None:
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

            # Сохраняем счётчик ходов до обновления памяти задачи
            orm.turns_since_task_memory = agent.turns_since_task_memory

            # Сохраняем current_phase
            orm.set_current_phase(agent.current_phase)

            # Сохраняем список подключённых MCP-серверов
            orm.set_mcp_servers(agent.connected_mcp_servers)

            session.commit()

            # После commit получаем сгенерированный ID, если это новый агент
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
        initial_phase: AgentPhase | None = None,
    ) -> Agent:
        """
        Создаёт нового агента и сохраняет в БД и файл.

        Returns:
            Agent: Новый экземпляр агента.
        """
        # Создаем агента с conversation_id - он будет установлен после сохранения ORM
        from uuid import uuid4

        temp_conversation_id = str(uuid4())  # Временный ID до сохранения в БД

        # Загружаем профиль задачи, если указан
        task_profile = None
        if task_profile_id is not None and self._task_profile_repository is not None:
            task_profile = self._task_profile_repository.get_profile_by_id(
                task_profile_id
            )

        agent = Agent(
            agent_id=None,  # Будет установлен после сохранения в БД
            conversation_id=temp_conversation_id,  # Временный ID, заменится после commit
            name=name,
            initial_settings=initial_settings,
            system_prompt=system_prompt,
            strategy=strategy,
            task_profile=task_profile,
            initial_phase=initial_phase,
        )

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
            orm.turns_since_task_memory = 0

            # Инициализируем фазу (по умолчанию plan)
            orm.set_current_phase(initial_phase or AgentPhase.PLAN)

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

            # Сортировка: None в конце, остальные по убыванию. SQLite может
            # вернуть naive datetime, поэтому нормализуем зону к UTC, иначе
            # сравнение naive и aware (fallback) падает с TypeError.
            def _sort_key(preview: AgentPreview) -> datetime:
                ts = preview.last_message_timestamp
                if ts is None:
                    return datetime.min.replace(tzinfo=UTC)
                if ts.tzinfo is None:
                    return ts.replace(tzinfo=UTC)
                return ts

            previews.sort(key=_sort_key, reverse=True)
            return previews

    def update_agent(self, agent: Agent) -> None:
        """
        Обновляет метаданные и историю агента.
        Вызывается агентом после каждого изменения состояния.

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

        # Удаляем память задачи диалога
        self.delete_task_memory(conversation_id)
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

            # Проверяем историю до гидратации: строим Agent только для тех,
            # у кого действительно есть несохранённые сообщения
            agents_with_unsaved = []
            for orm in orms:
                history = self._chat_storage.load_history(orm.conversation_id)
                unremembered_prompts = [
                    msg
                    for msg in history
                    if not msg.is_remembered and msg.role in ("user", "assistant")
                ]
                if unremembered_prompts:
                    agents_with_unsaved.append(
                        self._agent_orm_to_agent(orm, history=history)
                    )

            return agents_with_unsaved
