# AGENTS.md

## Project

AI Chat CLI — консольное приложение для взаимодействия с AI агентами (Yandex Cloud LLM via OpenAI-compatible API). Python >= 3.14.4, Poetry (`package-mode = false`, flat layout, no src package). README/docs/comments/UI strings are in Russian — keep new user-facing text and docstrings in Russian.

**Language**: общение с пользователем и все ответы вести на русском языке.

## Setup & commands

- `poetry install` — mandatory first step. Poetry's env is NOT in-project (configured `virtualenvs.in-project false`); the `.venv/` directory in the repo root is a stale artifact, ignore it. Run everything via `poetry run ...`.
- Run app: `poetry run python main_cli.py`
- Run web (REST API + built React) on :8080: `python main_api.py` — defaults to `APPLICATION_MODE=LOCAL` (override via env), serves both `/api/*` and `frontend/dist`. Single worker only (MCP state is in-process). Frontend build: `cd frontend && npm install && npm run build`.
- Run everything via Docker Compose: `docker compose up --build` — services `frontend` (nginx :3000, proxies `/api` → `web:8080`), `web` (:8080), `reranker` (:18080), `redis`, `worker`, `beat`. Mode `PROD`, data `./data`, Ollama — on the host (`host.docker.internal:11434`). The opencode dev container compose was renamed to `docker-compose.opencode.yml`. The web image is `python:3.14-alpine` (musl, for the vendored `vec0.so`) and deps are installed with Poetry (`requirements.txt` has `pywin32` and won't install on Linux).
- Lint: `poetry run ruff check --fix` (only `target-version = "py313"` configured).
- Tests (all are e2e; there is no unit test suite):
  - **NEVER run the full suite (`poetry run pytest cli_tests/`).** Its performance is unacceptable and the issue is unresolved. Always run only the specific test(s) relevant to the change.
  - Single case: `poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings::test_tc_001_quick_chat_creation_with_defaults -v`
  - E2E tests are split one file per test class (`cli_tests/test_ucXXX_*.py`); shared helpers live in `cli_tests/e2e_helpers.py`, the autouse cleanup fixture in `cli_tests/conftest.py`. `run_cli_command` itself asserts `returncode == 0` and empty `stderr`, so tests must not duplicate those checks and should discard unused tuple parts with `_` (avoids Ruff `RUF059`).
  - Smoke: `poetry run python cli_tests/smoke_test.py`
  - REST API tests (fast, in-process, `TestClient`): `poetry run pytest api_tests/test_api_smoke.py -v`
- `requirements.txt` mirrors pyproject deps as a pip fallback; Poetry + `poetry.lock` is primary.

## APPLICATION_MODE — the biggest gotcha

- `config.py` calls `load_dotenv()` and reads `APPLICATION_MODE` **at import time**. Set `os.environ["APPLICATION_MODE"] = "TEST"` BEFORE importing any project module (test files do this at the very top).
- `TEST` → MockLlmProvider, isolated storage under `./test-data/`. `LOCAL` → real providers (Ollama; Yandex only if keys present), no required env vars, isolated storage under `./local-data/`. Anything else (default `PROD`) → production: real Yandex API, storage under `./data/`, and startup fails with `OSError` unless `.env` defines `YANDEX_CLOUD_API_KEY` and `YANDEX_CLOUD_FOLDER`.
- E2E tests need no API keys: they spawn real `python main_cli.py` subprocesses driven through stdin keystrokes, and an autouse fixture wipes `./test-data/` before each test. Test names `test_tc_XXX_...` map to test cases in `docs/uc/` (one use case per file).
- `alembic/env.py` imports `DATABASE_URL` from `config.py`, so migrations target whichever DB the current `APPLICATION_MODE` selects. Note the app also auto-creates tables on startup (`DatabaseConnection.init_tables`), which additionally **adds missing columns** to existing SQLite tables (additive sync) — so schema drift on `create_all`-based DBs self-heals and `alembic upgrade head` is not needed for dev/tests.

## Architecture rules (enforced by README, verified in code)

Layers: `main_cli.py` (entry) → `app_factory.py` (DI: builds `UseCasesBundle`) → `cli_app.py` (presentation) → `use_cases.py` (business logic) → `agents.py` / `storage/` / `llm_providers.py` / `context_strategies.py`.

- `cli_app.py` may import ONLY from `use_cases` (plus the constant module `config` and stdlib) — no `storage.*`, `llm_providers`, `agents`, `context_strategies`, `mcp_registry`, `app_mode`, or `app_factory` imports. `celery_app.py`/`tasks.py` form a second presentation layer under the same constraint (they reach the system only via `app_factory.initialize_application()`). The REST API (`api/` + `main_api.py`) is a third presentation layer: `api/routers/*` import only `use_cases` (DTO) + `api.schemas` + stdlib; the only place that imports `app_factory` is `main_api.py` (bootstrap).
- **Presentation is DTO-only.** A presentation layer (`cli_app.py`, `api/`, Celery) must never see business objects (`Agent`, `TaskProfile`, …). It holds only an `agent_id`/`chat_id` and exchanges DTOs defined in (or re-exported from) `use_cases.py`. Use cases accept `agent_id` and/or DTOs and return DTOs; the `Agent` object never crosses the use-case boundary. A use case loads the agent internally via `repository.get_agent(agent_id)`.
- Agents self-persist: `Agent` has `save()` with `auto_save=True` on by default. Use cases must NOT call `repository.update_agent()` explicitly.
- Repositories receive a session factory; never create engines/connections inside repositories — `storage/db_connection.py::DatabaseConnection` owns that.
- Avoid N+1: construct `Agent` with everything it needs (e.g. `conversation_id`) in one query; no extra DB round-trips inside agent methods.

New feature flow: add use case file in `docs/uc/` and register it in the UC index table in `docs/cli_spec.md` → e2e test in `cli_tests/` (new file per test class) → use case class in `use_cases.py` → register field in `UseCasesBundle` in `app_factory.py` → call from `cli_app.py` → full e2e suite must pass.

## Celery (periodic agent reports)

- Requires Redis: `docker run -d --name redis-celery -p 6379:6379 redis:alpine` (override via `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`).
- Worker: `celery -A celery_app worker --loglevel=info --pool=solo` (`--pool=solo` is required on Windows). Beat: `celery -A celery_app beat --loglevel=info`.
- Reports are declared in `SCHEDULED_REPORTS` in `celery_app.py`; every entry is auto-scheduled to run once per minute.

## REST API / Web UI (FastAPI + React)

- Entry: `main_api.py` (bootstrap: `initialize_application()`) → `api/app.py::build_app(use_cases)`. Routers (`api/routers/*`) are DTO-only presentation; Pydantic schemas in `api/schemas.py`; domain-exception → HTTP mapping in `api/errors.py`; dependency `UseCasesDep` in `api/deps.py`.
- Serves REST under `/api/*` **and** the built React app from `frontend/dist` on one port (:8080). Single worker only (MCP state in-process). No streaming; document upload is `multipart` → temp file → existing `add_document` use case (no duplicated logic).
- **Auth**: all `/api/*` routes require `Authorization: Bearer <key>` except `/api/health` (enforced in `api/app.py` via `Depends(require_api_key)` from `api/security.py`). Keys are issued/revoked only from the CLI (main menu → `6. API-ключи`, UC-025); only a SHA-256 hash is stored. Tests create a key in the `client` fixture (see `api_tests/conftest.py`).
- Tests: `api_tests/` (in-process `TestClient`, `APPLICATION_MODE=TEST`).

## sqlite-vec (инфраструктура RAG)

- Расширение `sqlite-vec` вендорится в `storage/extensions/sqlite_vec/` (`vec0.so` для Linux/musl, `vec0.dll` для win_amd64). Загрузчик — `storage/extensions/sqlite_vec/__init__.py`; он вызывается из `storage/db_connection.py` через SQLAlchemy-событие `connect` на каждом соединении. Полная инструкция по пересборке/обновлению — `storage/extensions/sqlite_vec/INSTALL.md`.
- `pip install sqlite-vec` / добавление пакета в `pyproject.toml` **ломает установку на Alpine**: для musl нет ни колеса, ни sdist. Не добавлять `sqlite-vec` в зависимости.
- Пересборка musl-бинарника: `sh storage/extensions/sqlite_vec/build.sh` (нужен пакет `sqlite-dev` и `gcc`). Ключ `-include sys/types.h` обязателен на musl.
- Быстрая проверка (в т.ч. на Windows с `vec0.dll`): `poetry run python test_vec.py`.

## Секреты

- **Никогда не читай `.env`.** Этот файл содержит секреты (API-ключи, токены). Если нужно узнать переменную окружения — смотри `config.py`/документацию или переменные процесса, но не открывай `.env`. Это правило распространяется на любые `.env*`-файлы.

## Reranking (bge-reranker-v2-m3)

- Модель реранкинга `bge-reranker-v2-m3` на CPU работает в **отдельном HTTP-контейнере** `reranker_service/` (Python 3.12 + torch/sentence-transformers). Основной код на Python 3.14/Alpine torch не тянет — взаимодействие только по HTTP (TEI-совместимый `POST /rerank`).
- Переключатель per-chat: команда `/rerank on|off` (bare `/rerank` показывает состояние); по умолчанию реранкинг включён (`AgentSettings.reranker_enabled=True`). Состояние также видно в `/rag` и `/settings`.
- Запуск сервиса: `cd reranker_service && docker compose up --build` (порт 18080; на Windows — через Docker Desktop). Адрес — `RERANKER_BASE_URL` (по умолчанию `http://127.0.0.1:18080`, **не** `localhost`: на Windows `localhost` → `::1` и может попасть в чужой процесс), глобальный выключатель — `RERANKER_ENABLED`.
- В `APPLICATION_MODE=TEST` подключается `MockRerankerProvider` (без сети); в проде — `HttpRerankerProvider`. При недоступном сервисе `RagService` деградирует к векторному порядку (circuit breaker).

## Misc

- `mcp/` contains MCP servers (`time_mcp.py`, `open_alex_mcp.py`); root `*_mcp_test.py` files are manual test scripts for them, not pytest suites.
- Deeper docs: `README.md` (full architecture DO/DON'T list), `docs/cli_spec.md` (interface spec + UC index), `docs/uc/` (use cases with related test cases), `docs/cli_e2e_testing_guide.md` (testing practices/troubleshooting).
- No CI, no typecheck config, no pre-commit hooks.
