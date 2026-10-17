# AGENTS.md

## Project

AI Chat CLI — консольное приложение для взаимодействия с AI агентами (Yandex Cloud LLM via OpenAI-compatible API). Python >= 3.14.4, Poetry (`package-mode = false`, flat layout, no src package). README/docs/comments/UI strings are in Russian — keep new user-facing text and docstrings in Russian.

**Language**: общение с пользователем и все ответы вести на русском языке.

## Backlog

- `BACKLOG.md` в корне содержит известные несоответствия/потенциальные баги. **Пункты из `BACKLOG.md` НЕ выполнять (не исправлять, не менять код по ним) без явного указания пользователя.** Читать можно для контекста; при обнаружении новых проблем — дописывать в файл.

## Setup & commands

- `poetry install` — mandatory first step. Poetry's env is NOT in-project (configured `virtualenvs.in-project false`); the `.venv/` directory in the repo root is a stale artifact, ignore it. Run everything via `poetry run ...`.
- Run app: `poetry run python main_cli.py`
- Run web (REST API + built React) on :8080: `python main_api.py` — defaults to `APPLICATION_MODE=LOCAL` (override via env), serves both `/api/*` and `frontend/dist`. Single worker only (MCP state is in-process). Frontend build: `cd frontend && npm install && npm run build`.
- Run everything via Docker Compose: `docker compose up --build` — services `frontend` (nginx :3000, proxies `/api` → `web:8080`), `web` (:8080), `llm_gateway` (:18081, serializes access to Ollama), `reranker` (:18080), `redis`, `worker`, `beat`. Mode `PROD`, data `./data`, Ollama — on the host (`host.docker.internal:11434`). The opencode dev container compose was renamed to `docker-compose.opencode.yml`. The web image is `python:3.14-alpine` (musl, for the vendored `vec0.so`) and deps are installed with Poetry.
- Lint: `poetry run ruff check --fix` (only `target-version = "py313"` configured).
- Tests (details & policy: `docs/testing.md`):
  - Full suite: `poetry run pytest` — parallel by default (`pytest-xdist`, `-n auto` in `pyproject.toml [tool.pytest.ini_options]`). `testpaths` covers `core/tests`, `llm_gateway/tests`, `reranker_service/tests`, `mcp/tests`. Debug serially with `-n0`.
  - CLI e2e: `poetry run pytest core/tests/cli_tests`. One file per test class; shared helpers in `core/tests/e2e_helpers.py`, ground-truth accessors in `core/tests/ground_truth.py`, autouse cleanup fixture in `core/tests/cli_tests/conftest.py`. `run_cli_command` itself asserts `returncode == 0` and empty `stderr`, so tests must not duplicate those checks and should discard unused tuple parts with `_` (avoids Ruff `RUF059`).
  - **Assertions must prefer ground truth** (`ground_truth.py`: reads `agents.db` + pickles) over CLI-output substrings. `run_cli_command(input, mock=...)` injects a per-test scenario via `MOCK_LLM_SCENARIO` (see `core/infrastructure/llm/mock_scenario.py` / `e2e_helpers.mock_llm`); without it the default echo mock is used.
  - Core unit/integration: `poetry run pytest core/tests/core_tests`; REST API: `poetry run pytest core/tests/api_tests`; LLM Gateway: `poetry run pytest llm_gateway/tests`; Reranker: `poetry run pytest reranker_service/tests`; MCP: `poetry run pytest mcp/tests`.
  - Smoke: `poetry run python core/tests/cli_tests/smoke_test.py`
  - **Policy**: unit/integration tests are normally NOT written; when a behavior is too hard/impossible to verify via e2e, they are required. Such tests live in `core/tests/core_tests/` or next to the service.
  - `test-data*` dirs: cleaned/recreated before each test, orphaned ones removed at session start, all removed on a successful session (`pytest_sessionfinish` with exit code 0), kept on failure for debugging. `test-data*/` and `local-data*/` are in `.gitignore`.

## APPLICATION_MODE — the biggest gotcha

- `config.py` calls `load_dotenv()` and reads `APPLICATION_MODE` **at import time**. Set `os.environ["APPLICATION_MODE"] = "TEST"` BEFORE importing any project module (test files do this at the very top).
- `TEST` → MockLlmProvider, isolated storage under `./test-data/`. `LOCAL` → real providers (Ollama; Yandex only if keys present), no required env vars, isolated storage under `./local-data/`. Anything else (default `PROD`) → production: real Yandex API, storage under `./data/`, and startup fails with `OSError` unless `.env` defines `YANDEX_CLOUD_API_KEY` and `YANDEX_CLOUD_FOLDER`.
- E2E tests need no API keys: they spawn real `python main_cli.py` subprocesses driven through stdin keystrokes, and an autouse fixture wipes the per-worker `./test-data[-<worker>]/` before each test. Test names `test_tc_XXX_...` map to test cases in `docs/uc/` (one use case per file).
- `alembic/env.py` imports `DATABASE_URL` from `config.py`, so migrations target whichever DB the current `APPLICATION_MODE` selects. Note the app also auto-creates tables on startup (`DatabaseConnection.init_tables`), which additionally **adds missing columns** to existing SQLite tables (additive sync) — so schema drift on `create_all`-based DBs self-heals and `alembic upgrade head` is not needed for dev/tests.

## Architecture rules (enforced by README, verified in code)

Layers: `main_cli.py` / `main_api.py` (entry, остаются в корне) → `core/di/` (`app_factory.py` — DI: builds `UseCasesBundle`; `app_mode.py` — режимы работы) → `core/presentation/` (`cli/` → `cli_app.py`, `api/`, `celery/` → `celery_app.py`/`tasks.py`) → `core/application/` (application: `use_cases/` — один use case на файл, `dtos/`, `protocols/`, `exceptions/`, `services/`, `mappers/`, `adapters/`) → `core/domain/` (entities/DTOs/protocols/exceptions) + `core/infrastructure/` (`llm/`, `embeddings/`, `reranking/`, `persistence/`, `mcp/`, `files/`). `config.py` — в корне.

- **Domain core** lives in `core/domain/` with `entities/`, `dtos/`, `exceptions/` and `protocols/` (structural `Protocol` interfaces; one class per file everywhere). Domain modules must NOT import `core.infrastructure.*`, `core.application.*` or other outer layers. Infrastructure implements the domain/application protocols; dependencies (LLM provider, agent repository, tool executor, RAG result) are passed to entity methods as arguments and held by the use cases.
- **Application core** lives in `core/application/`: use cases (`use_cases/`), DTO (`dtos/`), порты (`protocols/`) и исключения (`exceptions/`) приложения. Use cases зависят только от протоколов (доменных из `core.domain.protocols` или собственных из `core.application.protocols`), а не от конкретной инфраструктуры. DTO-контракты, пересекающие границу «приложение ↔ инфраструктура» (напр. `VectorSearchItem`, `ChunkIngest`, `ApiKeyRecord`, `ExtractedFile`), принадлежат `core/application/dtos`; в инфраструктуре остаётся минимум DTO (внутренний `VectorInsertItem`).
- `core/presentation/cli/cli_app.py` may import ONLY from `core.application` subpackages (`core.application.dtos`, `core.application.exceptions`, `core.application.use_cases`) plus the constant module `config` and stdlib — no `core.infrastructure.*`, `core.domain`, `core.di.app_mode`, or `core.di.app_factory` imports. `core/presentation/celery/celery_app.py`/`tasks.py` form a second presentation layer under the same constraint (they reach the system only via `core.di.app_factory.initialize_application()`). The REST API (`core/presentation/api/` + `main_api.py`) is a third presentation layer: `core/presentation/api/routers/*` import only `core.application.dtos` + `core.application.use_cases` + `core.presentation.api.schemas` + stdlib; the only place that imports `core.di.app_factory` is `main_api.py` (bootstrap).
- **Presentation is DTO-only.** A presentation layer (`core/presentation/cli/`, `core/presentation/api/`, `core/presentation/celery/`) must never see business objects (`Agent`, `TaskProfile`, …). It holds only an `agent_id`/`chat_id` and exchanges DTOs defined in `core/application/dtos/` (or re-exported from `core.application.use_cases`). Use cases accept `agent_id` and/or DTOs and return DTOs; the `Agent` object never crosses the use-case boundary. A use case loads the agent internally via `repository.get_agent(agent_id)`.
- **Persistence is owned by the agent repository** (`PersistentAgentRepository` is the single gateway for chat metadata, history, global memory, per-chat task memory and task-profile facts). The `Agent` is a domain entity: it receives the repository per method (`agent.continue_dialog(..., repository=...)`, `agent.save(repository)`, `agent.refresh_memory(repository)`, …) and calls it to persist. Use cases still must NOT call `repository.update_agent()` explicitly — the agent triggers persistence itself. Repository implementations must NOT raise domain exceptions; **the agent fails fast** with `AgentPersistenceError` when the repository is missing (`None`) or when access to memory/history raises (wrapped as `MemoryAccessError`/`HistoryAccessError`). There is no silent degradation (e.g. an empty memory when the repo is absent).
- Repositories receive a session factory; never create engines/connections inside repositories — `core/infrastructure/persistence/db_connection.py::DatabaseConnection` owns that.
- Avoid N+1: construct `Agent` with everything it needs (e.g. `conversation_id`) in one query; no extra DB round-trips inside agent methods.

New feature flow: add use case file in `docs/uc/` and register it in the UC index table in `docs/cli_spec.md` → e2e test in `core/tests/cli_tests/` (new file per test class) → use case class in `core/application/use_cases/<snake_case>.py` (+ re-export in `core/application/use_cases/__init__.py`) → register field in `UseCasesBundle` (`core/application/use_cases/bundle.py`) → wire concrete deps in `core/di/app_factory.py` → call from `core/presentation/cli/cli_app.py` → full e2e suite must pass.

## Celery (periodic agent reports)

- Requires Redis: `docker run -d --name redis-celery -p 6379:6379 redis:alpine` (override via `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`).
- Worker: `celery -A core.presentation.celery.celery_app worker --loglevel=info --pool=solo` (`--pool=solo` is required on Windows). Beat: `celery -A core.presentation.celery.celery_app beat --loglevel=info`.
- Reports are declared in `SCHEDULED_REPORTS` in `core/presentation/celery/celery_app.py`; every entry is auto-scheduled to run once per minute.

## REST API / Web UI (FastAPI + React)

- Entry: `main_api.py` (bootstrap: `initialize_application()`) → `core/presentation/api/app.py::build_app(use_cases)`. Routers (`core/presentation/api/routers/*`) are DTO-only presentation; Pydantic schemas in `core/presentation/api/schemas.py`; domain-exception → HTTP mapping in `core/presentation/api/errors.py`; dependency `UseCasesDep` in `core/presentation/api/deps.py`.
- Serves REST under `/api/*` **and** the built React app from `frontend/dist` on one port (:8080). Single worker only (MCP state in-process). No streaming; document upload is `multipart` → temp file → existing `add_document` use case (no duplicated logic).
- **Auth**: all `/api/*` routes require `Authorization: Bearer <key>` except `/api/health` (enforced in `core/presentation/api/app.py` via `Depends(require_api_key)` from `core/presentation/api/security.py`). Keys are issued/revoked only from the CLI (main menu → `6. API-ключи`, UC-025); only a SHA-256 hash is stored. Tests create a key in the `client` fixture (see `core/tests/api_tests/conftest.py`).
- Tests: `core/tests/api_tests/` (in-process `TestClient`, `APPLICATION_MODE=TEST`).

## sqlite-vec (инфраструктура RAG)

- Расширение `sqlite-vec` вендорится в `core/infrastructure/persistence/extensions/sqlite_vec/` (`vec0.so` для Linux/musl, `vec0.dll` для win_amd64). Загрузчик — `core/infrastructure/persistence/extensions/sqlite_vec/__init__.py`; он вызывается из `core/infrastructure/persistence/db_connection.py` через SQLAlchemy-событие `connect` на каждом соединении. Полная инструкция по пересборке/обновлению — `core/infrastructure/persistence/extensions/sqlite_vec/INSTALL.md`.
- `pip install sqlite-vec` / добавление пакета в `pyproject.toml` **ломает установку на Alpine**: для musl нет ни колеса, ни sdist. Не добавлять `sqlite-vec` в зависимости.
- Пересборка musl-бинарника: `sh core/infrastructure/persistence/extensions/sqlite_vec/build.sh` (нужен пакет `sqlite-dev` и `gcc`). Ключ `-include sys/types.h` обязателен на musl.
- Быстрая проверка (в т.ч. на Windows с `vec0.dll`): `poetry run python scripts/check_sqlite_vec.py`.

## Секреты

- **Никогда не читай `.env`.** Этот файл содержит секреты (API-ключи, токены). Если нужно узнать переменную окружения — смотри `config.py`/документацию или переменные процесса, но не открывай `.env`. Это правило распространяется на любые `.env*`-файлы.

## Reranking (bge-reranker-v2-m3)

- Модель реранкинга `bge-reranker-v2-m3` на CPU работает в **отдельном HTTP-контейнере** `reranker_service/` (Python 3.12 + torch/sentence-transformers). Основной код на Python 3.14/Alpine torch не тянет — взаимодействие только по HTTP (TEI-совместимый `POST /rerank`).
- Переключатель per-chat: команда `/rerank on|off` (bare `/rerank` показывает состояние); по умолчанию реранкинг включён (`AgentSettings.reranker_enabled=True`). Состояние также видно в `/rag` и `/settings`.
- Запуск сервиса: `cd reranker_service && docker compose up --build` (порт 18080; на Windows — через Docker Desktop). Адрес — `RERANKER_BASE_URL` (по умолчанию `http://127.0.0.1:18080`, **не** `localhost`: на Windows `localhost` → `::1` и может попасть в чужой процесс), глобальный выключатель — `RERANKER_ENABLED`.
- В `APPLICATION_MODE=TEST` подключается `MockRerankerProvider` (без сети); в проде — `HttpRerankerProvider`. При недоступном сервисе `RagService` деградирует к векторному порядку (circuit breaker).

## LLM Gateway (единый поток запросов к Ollama)

- Ollama плохо переносит параллельные запросы, а её нагружают CLI, REST API, Celery и (в будущем) сабагенты. Сервис `llm_gateway/` (Python 3.14, отдельный контейнер `ai_chat_llm_gateway`, порт 18081) — **единственный, кто ходит в Ollama напрямую**. Он принимает Ollama-совместимые запросы (`/v1/chat/completions`, `/api/embed`, `/api/tags`) и сериализует их через очередь: одновременно в Ollama уходит ровно один запрос, остальные ждут.
- Очередь — Redis Streams (durable) при заданном `LLM_GATEWAY_REDIS_URL`; пусто ⇒ in-process очередь (dev/тесты). Ответ отдаётся через per-request reply-list; «зависшие» задачи переклэймливаются (`XAUTOCLAIM`).
- Бэкенд не меняет код провайдеров: `OllamaLlmProvider`/`OllamaEmbeddingProvider` работают по OpenAI/Ollama-API, но базовые URL при `LLM_GATEWAY_ENABLED=true` указывают на gateway (`OLLAMA_NATIVE_BASE_URL`, `OLLAMA_OPENAI_BASE_URL`, `EMBEDDING_BASE_URL` в `config.py`). В `TEST` шлюз выключен (mock-провайдеры).
- **Ровно одна реплика gateway.** Гарантия «один запрос в Ollama» держится на единственном потребителе очереди; несколько реплик/потребителей её ломают (это же правило зафиксировано в README DON'T).
- При недоступности gateway/Redis — **fail fast** (503/504), без обхода в Ollama. Backpressure — `MAX_QUEUE_DEPTH`; таймауты: gateway `QUEUE_WAIT_TIMEOUT`/`LLM_UPSTREAM_TIMEOUT`, бэкенд `LLM_REQUEST_TIMEOUT`/`MEMORY_LLM_TIMEOUT`/`EMBEDDING_TIMEOUT` (должны перекрывать ожидание в очереди).
- Gateway использует Redis DB `2` (`LLM_GATEWAY_REDIS_URL`), Celery — `0/1`.
- Тесты: `poetry run pytest llm_gateway/tests -v` (in-process очередь + стаб upstream, без сети). Локальный запуск без Docker: `python -m llm_gateway.main`.

## Misc

- `mcp/` contains MCP servers (`time_mcp.py`, `open_alex_mcp.py`); their pytest wrappers live in `mcp/tests/` (spawn the servers; network MCP cases skip when unavailable).
- Deeper docs: `README.md` (full architecture DO/DON'T list), `docs/cli_spec.md` (interface spec + UC index), `docs/uc/` (use cases with related test cases), `docs/cli_e2e_testing_guide.md` (testing practices: ground truth, scenario mocks, performance, troubleshooting).
- No CI, no typecheck config, no pre-commit hooks.
