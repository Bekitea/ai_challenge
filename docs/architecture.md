# Архитектура AI Chat CLI

Единый источник правды по устройству системы: слои, ключевые архитектурные
решения и правила разработки. Спецификация интерфейса — в
[`cli_spec.md`](cli_spec.md), тесты — в [`testing.md`](testing.md), инварианты
для AI-агентов — в [`../AGENTS.md`](../AGENTS.md).

## 1. Обзор и принципы

Приложение построено по принципу **чистой архитектуры** с чётким разделением
ответственности между слоями. Ядро вынесено в `core/` и разделено на слои (в
каждом — правило «одному классу свой файл»).

- Зависимости направлены **внутрь**: внешние слои знают о внутренних, но не
  наоборот. Домен не знает о слое приложения и инфраструктуре.
- Провайдер LLM, репозиторий агента, исполнитель инструментов и RAG-результат
  передаются в методы сущностей **как аргументы** и хранятся в use cases.
- Use cases зависят только от протоколов (доменных из `core.domain.protocols`
  или собственных из `core.application.protocols`), а конкретные реализации
  собираются фабрикой `core/di/app_factory.py`.

## 2. Слои и структура

```
core/
├── domain/          # бизнес-ядро (не зависит от внешних слоёв)
│   ├── entities/    # бизнес-сущности (Agent, стратегии, PromptBuilder …)
│   ├── dtos/        # простые структуры данных
│   ├── exceptions/  # доменные исключения
│   └── protocols/   # структурные Protocol-интерфейсы
├── application/     # бизнес-логика (use cases) + порты
│   ├── use_cases/   # по одному use case на файл
│   ├── dtos/        # контракты «приложение ↔ инфраструктура»
│   ├── protocols/   # порты, реализуемые инфраструктурой
│   ├── exceptions/
│   ├── services/    # RAG-сервисы
│   ├── mappers/
│   └── adapters/
├── infrastructure/  # провайдеры и репозитории (реализуют порты)
│   ├── llm/         # Yandex Cloud / Ollama / Mock провайдеры, реестр
│   ├── embeddings/  # OllamaEmbeddingProvider
│   ├── reranking/   # HttpRerankerProvider / MockRerankerProvider
│   ├── persistence/ # репозитории, ORM, sqlite-vec, file storage
│   ├── mcp/         # MCP-реестр и подключения
│   └── files/       # работа с файлами
├── di/              # app_factory.py (DI: сборка UseCasesBundle),
│                    # app_mode.py (режимы работы приложения)
└── presentation/    # слои представления
    ├── cli/         # cli_app.py
    ├── api/         # FastAPI REST
    └── celery/      # celery_app.py, tasks.py
```

Точки входа (`main_cli.py`, `main_api.py`) и константы (`config.py`) остаются
**в корне** проекта.

### 2.1 Точки входа

- `main_cli.py` — только оркестрация: выставляет `APPLICATION_MODE`, вызывает
  фабрику, создаёт CLI-приложение, обрабатывает глобальные исключения. Никакой
  бизнес-логики.
- `main_api.py` — bootstrap REST API: `initialize_application()` →
  `build_app(use_cases)`. Единственное место, которое импортирует
  `core.di.app_factory`.
- `config.py` — константы окружения; `load_dotenv()` и чтение
  `APPLICATION_MODE` происходят **при импорте**.

### 2.2 `core/di/` — фабрика

`app_factory.py` определяет режим работы (через `app_mode`), валидирует
переменные окружения, создаёт реестр LLM-провайдеров (`LlmProviderRegistry`),
инициализирует репозитории, создаёт все use cases и возвращает их в
`UseCasesBundle`. Слой представления не знает о режимах работы — фабрика
инкапсулирует эту логику.

### 2.3 `core/presentation/` — представление (DTO-only)

Три слоя представления под одним ограничением: **никогда не видят бизнес-объект
`Agent`** (или `TaskProfile`). Они хранят только `agent_id`/`chat_id` и
обмениваются DTO из `core/application/dtos/`. Use case сам загружает агента
внутри по `agent_id`; объект `Agent` не пересекает границу use case.

- `cli/` (`cli_app.py`) — импортирует только `core.application` (DTO и
  `UseCasesBundle`), `config` и stdlib. Запрещены `core.infrastructure.*`,
  `core.domain.*`, `core.di.app_mode.*`, `core.di.app_factory.*`.
- `api/` (FastAPI) — `routers/*` импортируют только `core.application.dtos` +
  `core.application.use_cases` + `core.presentation.api.schemas` + stdlib.
- `celery/` (`celery_app.py`, `tasks.py`) — вторая presentation-слой; достигает
  систему только через `core.di.app_factory.initialize_application()`.

### 2.4 `core/application/` — бизнес-логика

Инкапсулирует всю бизнес-логику (`use_cases/`, один use case на файл),
координирует репозитории, агентов и провайдеров, предоставляет чистый интерфейс
для CLI/API. Содержит порты (`protocols/`), DTO (`dtos/`) и исключения
(`exceptions/`), а также `services/` (RAG), `mappers/`, `adapters/`.

DTO-контракты, пересекающие границу «приложение ↔ инфраструктура» (например,
`VectorSearchItem`, `ChunkIngest`, `ApiKeyRecord`, `ExtractedFile`), принадлежат
`core.application.dtos`.

### 2.5 `core/domain/` — бизнес-ядро

`entities/` (сущности `Agent`, `AgentPhase`, стратегии контекста,
`PromptBuilder`), `dtos/`, `exceptions/`, `protocols/`. Домен **не импортирует**
`core.infrastructure.*`, `core.application.*` и другие внешние слои.

### 2.6 `core/infrastructure/` — провайдеры и репозитории

- `persistence/` — `db_connection.py` (единственный владелец подключений),
  `persistent_agent_repository.py` (единый шлюз персистентности),
  `conversation_repository.py`, `orm/` (SQLAlchemy-модели), `sqlite_*.py`
  (RAG-репозитории), `sqlite_vec_vector_store.py` (вектора sqlite-vec),
  `file_task_memory_repository.py` (память задачи диалога).
- `llm/` — `YandexCloudLlmProvider`, `OllamaLlmProvider`, `MockLlmProvider`,
  `llm_provider_registry.py`, `mock_scenario.py`. Список моделей не хардкодится
  (UC-023); у каждой модели указан провайдер; провайдера по умолчанию нет.
- `embeddings/` — `OllamaEmbeddingProvider`.
- `reranking/` — `HttpRerankerProvider` (HTTP-сервис `reranker_service/`),
  `MockRerankerProvider` (тест).
- `mcp/`, `files/` — MCP-реестр/подключения и файловые операции.

**Важно:** репозитории не создают соединения/движки внутри себя; они получают
фабрику сессий как внешнюю зависимость. Управление подключениями
инкапсулировано в `DatabaseConnection`.

## 3. Поток управления

```
┌─────────────────────────────────────────────────────────┐
│                    main_cli.py                          │
│              (Точка входа, только оркестрация)          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               core/di/app_factory.py                     │
│    (Фабрика: инициализация компонентов по режиму)       │
│  - Определяет режим (production/test)                   │
│  - Создает реестр LLM провайдеров (YandexCloud/Ollama/Mock) │
│  - Инициализирует репозитории                           │
│  - Создает и возвращает UseCasesBundle                  │
└────────────────────┬────────────────────────────────────┘
                     │ UseCasesBundle
                     ▼
┌─────────────────────────────────────────────────────────┐
│         core/presentation/cli/cli_app.py                │
│            (CLI слой представления)                     │
│  - Отображение меню и ввод пользователя                 │
│  - Форматирование вывода                                │
│  - Вызов use cases для бизнес-логики                    │
│  - НЕ знает о режимах, репозиториях, LLM провайдерах    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           core/application/                             │
│           (Слой бизнес-логики/Use Cases)                │
│  - use_cases/ (CreateChatUseCase, SendMessageUseCase, …)│
│  - dtos/, protocols/, exceptions/, services/            │
│  - Координируют работу репозиториев и агентов           │
│  - Инкапсулируют всю бизнес-логику приложения           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           core/domain/ + core/infrastructure/           │
│  domain: entities/, dtos/, protocols/, exceptions/      │
│  infrastructure: persistence/, llm/, embeddings/,       │
│    reranking/, mcp/, files/                             │
└─────────────────────────────────────────────────────────┘
```

## 4. Ключевые архитектурные решения

### 4.1 Инкапсуляция сохранения состояния агента

Сохранение состояния, памяти и истории агента выполняет **репозиторий агента**
(`PersistentAgentRepository`), который агент получает **аргументом нужного
метода** (use cases хранят репозиторий и передают его).

1. **Агент отвечает за своё состояние** — `Agent.save(repository)` вызывается
   при изменениях.
2. **Репозиторий — единый шлюз персистентности** — история, глобальная память,
   память задачи и факты профиля сохраняются/читаются через него.
3. **Use cases не управляют сохранением** — никаких явных
   `repository.update_agent()` в бизнес-логике.
4. **Fail-fast без инфраструктуры** — если репозиторий не передан (`None`),
   агент падает с `AgentPersistenceError`; ошибки доступа оборачиваются в
   `MemoryAccessError`/`HistoryAccessError`. Тихая деградация (пустая память
   вместо ошибки) запрещена.

Агент сохраняется автоматически: при изменении настроек (`update_settings()`),
после каждого сообщения (`continue_dialog()`), при переходе фаз и
подключении/отключении MCP.

Преимущества: единая точка ответственности за сохранение; use cases чисты от
инфраструктурных деталей; репозиторий — протокол, легко подменяется в тестах;
объект сам управляет своим состоянием.

### 4.2 DTO-only граница представления

Presentation-слой никогда не видит бизнес-объекты (`Agent`, `TaskProfile`, …).
Он оперирует только `agent_id`/`chat_id` и DTO, определёнными в
`core/application/dtos/` (или реэкспортированными из `use_cases`). Use cases
принимают `agent_id` и/или DTO и возвращают DTO. Правило распространяется на
CLI, REST API и Celery.

### 4.3 Стратегии управления контекстом

Стратегии отвечают **только** за контекстное окно: какие диалоговые сообщения
отправить в LLM и какое саммари к ним добавить. Всё подмешивание памяти, профиля
задачи и фазы — ответственность `PromptBuilder`.

Интерфейс: `ContextWindowStrategy.apply(dialogue, llm_provider) -> WindowResult`.
Общая логика суммаризации вынесена в `BaseCompressionStrategy`. Один класс — один
файл (`default_strategy.py`, `summarization_strategy.py`,
`key_value_memory_strategy.py`, `sliding_window_strategy.py`):

- `DefaultStrategy` — пересылка всех сообщений;
- `SummarizationStrategy` — суммаризация истории;
- `KeyValueMemoryStrategy` — JSON-суммаризация по ключевым категориям;
- `SlidingWindowStrategy` — скользящее окно последних N сообщений.

### 4.4 `PromptBuilder` — единая сборка контекста

`PromptBuilder` — единственная точка, где в контекст модели подмешиваются:
базовый системный промпт (персона), глобальная память, память/предпочтения/
инварианты профиля задачи, per-chat память задачи (цель, ограничения, термины,
уточнения), описание текущей фазы и саммари истории от стратегии.

`PromptBuilder.build(history, PromptSources, strategy, llm_provider)` формирует
ровно один базовый system-блок в фиксированном порядке и возвращает
`PreparedMessages`. Агент хранит ссылку на `PromptBuilder` и вызывает его из
`continue_dialog`.

### 4.5 Память задачи диалога (per-chat)

Гибридная память: `TaskProfile` (общие факты/инварианты) остаётся, а per-chat
`TaskMemory` (цель, ограничения, термины, уточнения) хранится по
`conversation_id` в pickle-файлах `{FILE_STORAGE_DIR}/task_memory/`. Она
подмешивается в system-промпт на каждом сообщении. Обновление
(`Agent.update_task_memory`) идёт через LLM каждые N ходов и при сжатии
контекста; новые уточнения перекрывают устаревшие. Ветка (`/branch`) стартует с
пустой памятью задачи.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `TASK_MEMORY_ENABLED` | `true` | Глобальный выключатель памяти задачи |
| `TASK_MEMORY_UPDATE_EVERY_N_MESSAGES` | `3` | Как часто обновлять (в ходах) |
| `TASK_MEMORY_WINDOW_MESSAGES` | `12` | Сколько последних сообщений анализировать |

Профиль задачи можно привязать только при создании чата; подробности — в
[`uc/uc-022`](uc/uc-022-task-memory.md).

### 4.6 RAG и реранкинг

- `core/application/services/` — `RagService`, `RagModelService`, `chunking`.
- `core/infrastructure/embeddings/` — `OllamaEmbeddingProvider`.
- `core/infrastructure/reranking/` — `HttpRerankerProvider`, `MockRerankerProvider`.
- `reranker_service/` — отдельный CPU-контейнер с моделью `bge-reranker-v2-m3`
  (TEI-совместимый `POST /rerank`). При недоступном сервисе `RagService`
  деградирует к векторному порядку (circuit breaker). В `TEST` подключается
  `MockRerankerProvider`.

Запуск и настройка реранкера — в [`../README.md`](../README.md).

### 4.7 LLM Gateway — единый поток запросов к Ollama

Ollama плохо переносит параллельные запросы, а её нагружают CLI, REST API, Celery
и (в будущем) сабагенты. `llm_gateway/` (Python 3.14, отдельный контейнер, порт
18081) — **единственный, кто ходит в Ollama напрямую**. Он принимает
Ollama-совместимые запросы (`/v1/chat/completions`, `/api/embed`, `/api/tags`) и
сериализует их через очередь (Redis Streams, durable; иначе in-process):
одновременно в Ollama уходит ровно один запрос.

Провайдеры не меняются: `OllamaLlmProvider`/`OllamaEmbeddingProvider` работают
по OpenAI/Ollama-API, но базовые URL при `LLM_GATEWAY_ENABLED=true` указывают на
gateway (`OLLAMA_NATIVE_BASE_URL`, `OLLAMA_OPENAI_BASE_URL`,
`EMBEDDING_BASE_URL`). В `TEST` шлюз выключен (mock-провайдеры).

При недоступности gateway/Redis — **fail fast** (503/504). Держать ровно
**одну реплику** gateway: гарантия «один запрос в Ollama» держится на
единственном потребителе очереди.

### 4.8 Режимы `APPLICATION_MODE`

`config.py` читает `APPLICATION_MODE` **при импорте** — выставляйте его до
импорта модулей проекта.

- `TEST` → `MockLlmProvider`, изолированное хранилище `./test-data/`.
- `LOCAL` → реальные провайдеры (Ollama; Yandex — только при наличии ключей),
  изолированное хранилище `./local-data/`.
- иное (по умолчанию `PROD`) → реальный Yandex API, `./data/`, старт падает с
  `OSError` без `YANDEX_CLOUD_API_KEY`/`YANDEX_CLOUD_FOLDER`.

`alembic/env.py` импортирует `DATABASE_URL` из `config.py`, поэтому миграции
таргетят БД текущего режима. Приложение также само создаёт таблицы и
досинхронизирует недостающие колонки при старте (`DatabaseConnection.init_tables`).

## 5. Правила разработки

### 5.1 ✅ DO (Делайте)

1. **Выносите новую бизнес-логику в use cases и агента.** Новая функциональность
   — новый use case или расширение существующего; use case инкапсулирует всю
   логику взаимодействия с репозиториями и агентами. Логика сохранения состояния
   — в самом агенте, не в use cases.
2. **CLI-слой работает только с use cases.** `cli_app.py` импортирует только из
   `core.application` (DTO/`use_cases`) и `config`. Запрещены прямые импорты
   репозиториев, LLM-провайдеров, агентов.
3. **Используйте фабрику для инициализации.** Вся логика создания объектов — в
   `core/di/app_factory.py`; CLI получает готовые use cases.
4. **Пишите e2e-тесты для новой функциональности.** Каждый use case покрыт хотя
   бы одним e2e-тестом; спецификация — в `docs/uc/` и `docs/cli_spec.md`. См.
   [`testing.md`](testing.md).
5. **Следуйте принципу единственной ответственности.** `main_cli`/`main_api` →
   оркестрация; `core.di` → инициализация; `core.presentation` → UI/UX;
   `core.application`/`core.domain` → бизнес-логика; `core.infrastructure` →
   инфраструктура.
6. **Агент отвечает за своё сохранение.** `Agent.save(repository)` вызывается
   при изменениях; use cases не вызывают `repository.update_agent()`. Без
   репозитория — fail-fast (`AgentPersistenceError`).
7. **Минимизируйте число запросов к БД (ORM).** Загружайте всё нужное сразу при
   первом обращении к агенту; избегайте лишних join'ов и повторных запросов
   внутри методов агента (например, `conversation_id` уже в объекте). Проверяйте
   код на N+1.

### 5.2 ❌ DON'T (Не делайте)

1. **Не добавляйте бизнес-логику в CLI-слой.**

   ```python
   # ПЛОХО: в core/presentation/cli/cli_app.py
   agent = repository.get_agent(agent_id)  # Прямой вызов репозитория

   # ХОРОШО: через use case
   agent = self.use_cases.select_chat.get_agent(agent_id)
   ```

2. **Не импортируйте инфраструктурные зависимости в CLI.**

   ```python
   # ПЛОХО: в core/presentation/cli/cli_app.py
   from core.infrastructure.persistence.persistent_agent_repository import PersistentAgentRepository
   from core.infrastructure.llm.yandex_cloud_llm_provider import YandexCloudLlmProvider

   # ХОРОШО: только слой приложения
   from core.application.use_cases import UseCasesBundle
   ```

3. **Не создавайте бизнес-объекты напрямую в CLI.**

   ```python
   # ПЛОХО: в core/presentation/cli/cli_app.py
   strategy = SummarizationStrategy(non_compressible_count=2, buffer_size=3)

   # ХОРОШО: через use case
   selection = StrategySelection(strategy_type="SummarizationStrategy", ...)
   strategy = self.use_cases.select_strategy.execute(selection)
   ```

4. **Не смешивайте режимы работы в CLI.**

   ```python
   # ПЛОХО: в core/presentation/cli/cli_app.py
   if os.environ.get("APPLICATION_MODE") == "TEST":
       provider = MockLlmProvider()

   # ХОРОШО: фабрика скрывает эту логику
   use_cases = initialize_application()  # Фабрика сама определит режим
   ```

5. **Не создавайте соединения с БД в репозиториях.**

   ```python
   # ПЛОХО: в репозитории
   class PersistentAgentRepository:
       def __init__(self, db_path):
           self.engine = create_engine(f"sqlite:///{db_path}")


   # ХОРОШО: репозиторий получает фабрику сессий
   class PersistentAgentRepository:
       def __init__(self, session_factory):
           self._session_factory = session_factory
   ```

6. **Не вызывайте `repository.update_agent()` из use cases для сохранения агента.**

   ```python
   # ПЛОХО: в use case
   class SendMessageUseCase:
       def execute(self, agent, message):
           response = agent.continue_dialog(message)
           self.repository.update_agent(agent)  # ❌ Явное сохранение


   # ХОРОШО: агент самосохраняется через переданный репозиторий
   class SendMessageUseCase:
       def execute(self, agent, message):
           response = agent.continue_dialog(  # ✅ Агент сам сохранит
               message, repository=self.repository, llm_provider=provider
           )
           return response, agent
   ```

7. **Не делайте лишние запросы к БД при работе с ORM.**

   ```python
   # ПЛОХО: conversation_id запрашивается из БД на каждый вызов метода
   class Agent:
       def _save_agent_history(self, messages):
           # ❌ Отдельный запрос к БД внутри метода
           conv_id = self._repository.get_conversation_id(self.id)
           self._chat_storage.save(conv_id, messages)

   # ХОРОШО: conversation_id загружен один раз при инициализации агента
   class Agent:
       def __init__(self, ..., conversation_id: UUID):
           self._conversation_id = conversation_id  # ✅ Загружено заранее

       def _save_agent_history(self, messages):
           # Использует уже загруженное значение без запроса к БД
           self._chat_storage.save(self._conversation_id, messages)

   # В репозитории - загрузка всех данных одним запросом:
   def get_agent(self, agent_id: int) -> Agent:
       with self._session_factory() as session:
           db_agent = session.query(AgentORM).filter_by(id=agent_id).first()
           # ✅ Возвращаем агента со всеми данными, включая conversation_id
           return Agent(id=db_agent.id, conversation_id=db_agent.conversation_id, ...)
   ```

8. **Не ходите в Ollama в обход `llm_gateway` и не масштабируйте его.**

   - В PROD/LOCAL обращения к Ollama (чат, эмбеддинги, список моделей) — только
     через `llm_gateway`.
   - Ровно **одна** реплика/один потребитель очереди gateway.
   - В `TEST` шлюз не нужен — там mock-провайдеры.

## 6. Добавление новой функциональности

1. **Спецификация** — создайте файл use case в `docs/uc/` (альтернативные потоки
   и test cases) и зарегистрируйте в таблице-индексе `docs/cli_spec.md`.
2. **Тесты** — добавьте test case в файл use case, реализуйте e2e-тест в
   `core/tests/cli_tests/` (отдельный файл на класс), запустите
   `poetry run pytest core/tests/cli_tests` (все тесты, кроме нового, должны
   проходить).
3. **Use case** — новый класс в `core/application/use_cases/<snake_case>.py` (один
   use case на файл) + реэкспорт в `__init__.py`. Зависимости — только протоколы
   (`core.domain.protocols`, `core.application.protocols`) и DTO
   (`core.application.dtos`).
4. **Bundle** — добавьте поле в `UseCasesBundle`
   (`core/application/use_cases/bundle.py`).
5. **Фабрика** — создайте экземпляр в `core/di/app_factory.py` (конкретные
   зависимости — из `core.infrastructure`) и передайте в bundle.
6. **CLI** — вызовите `self.use_cases.<new_use_case>.execute(...)` в
   `core/presentation/cli/cli_app.py`, обработайте и отобразите результат.
7. **Проверка** — `poetry run pytest core/tests/cli_tests`; все тесты должны
   пройти.
