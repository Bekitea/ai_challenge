# AGENTS.md

## Project

AI Chat CLI — консольное приложение для взаимодействия с AI агентами (Yandex Cloud LLM via OpenAI-compatible API). Python >= 3.14.4, Poetry (`package-mode = false`, flat layout, no src package). README/docs/comments/UI strings are in Russian — keep new user-facing text and docstrings in Russian.

**Language**: общение с пользователем и все ответы вести на русском языке.

## Setup & commands

- `poetry install` — mandatory first step. Poetry's env is NOT in-project (configured `virtualenvs.in-project false`); the `.venv/` directory in the repo root is a stale artifact, ignore it. Run everything via `poetry run ...`.
- Run app: `poetry run python main_cli.py`
- Lint: `poetry run ruff check --fix` (only `target-version = "py313"` configured).
- Tests (all are e2e; there is no unit test suite):
  - `poetry run pytest cli_tests/ -v`
  - Single case: `poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings::test_tc_001_quick_chat_creation_with_defaults -v`
  - E2E tests are split one file per test class (`cli_tests/test_ucXXX_*.py`); shared helpers live in `cli_tests/e2e_helpers.py`, the autouse cleanup fixture in `cli_tests/conftest.py`. `run_cli_command` itself asserts `returncode == 0` and empty `stderr`, so tests must not duplicate those checks and should discard unused tuple parts with `_` (avoids Ruff `RUF059`).
  - Smoke: `poetry run python cli_tests/smoke_test.py`
- `requirements.txt` mirrors pyproject deps as a pip fallback; Poetry + `poetry.lock` is primary.

## APPLICATION_MODE — the biggest gotcha

- `config.py` calls `load_dotenv()` and reads `APPLICATION_MODE` **at import time**. Set `os.environ["APPLICATION_MODE"] = "TEST"` BEFORE importing any project module (test files do this at the very top).
- `TEST` → MockLlmProvider, isolated storage under `./test-data/`. Anything else (default) → production: real Yandex API, storage under `./data/`, and startup fails with `OSError` unless `.env` defines `YANDEX_CLOUD_API_KEY` and `YANDEX_CLOUD_FOLDER`.
- E2E tests need no API keys: they spawn real `python main_cli.py` subprocesses driven through stdin keystrokes, and an autouse fixture wipes `./test-data/` before each test. Test names `test_tc_XXX_...` map to test cases in `docs/uc/` (one use case per file).
- `alembic/env.py` imports `DATABASE_URL` from `config.py`, so migrations target whichever DB the current `APPLICATION_MODE` selects. Note the app also auto-creates tables on startup (`DatabaseConnection.init_tables`), so `alembic upgrade head` is not needed for dev/tests.

## Architecture rules (enforced by README, verified in code)

Layers: `main_cli.py` (entry) → `app_factory.py` (DI: builds `UseCasesBundle`) → `cli_app.py` (presentation) → `use_cases.py` (business logic) → `agents.py` / `storage/` / `llm_providers.py` / `context_strategies.py`.

- `cli_app.py` may import ONLY from `use_cases` — no `storage.*`, `llm_providers`, `agents`, `app_mode`, or `app_factory` imports. `celery_app.py`/`tasks.py` form a second presentation layer under the same constraint (they reach the system only via `app_factory.initialize_application()`).
- Agents self-persist: `Agent` has `save()` with `auto_save=True` on by default. Use cases must NOT call `repository.update_agent()` explicitly.
- Repositories receive a session factory; never create engines/connections inside repositories — `storage/db_connection.py::DatabaseConnection` owns that.
- Avoid N+1: construct `Agent` with everything it needs (e.g. `conversation_id`) in one query; no extra DB round-trips inside agent methods.

New feature flow: add use case file in `docs/uc/` and register it in the UC index table in `docs/cli_spec.md` → e2e test in `cli_tests/` (new file per test class) → use case class in `use_cases.py` → register field in `UseCasesBundle` in `app_factory.py` → call from `cli_app.py` → full e2e suite must pass.

## Celery (periodic agent reports)

- Requires Redis: `docker run -d --name redis-celery -p 6379:6379 redis:alpine` (override via `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`).
- Worker: `celery -A celery_app worker --loglevel=info --pool=solo` (`--pool=solo` is required on Windows). Beat: `celery -A celery_app beat --loglevel=info`.
- Reports are declared in `SCHEDULED_REPORTS` in `celery_app.py`; every entry is auto-scheduled to run once per minute.

## Misc

- `mcp/` contains MCP servers (`time_mcp.py`, `open_alex_mcp.py`); root `*_mcp_test.py` files are manual test scripts for them, not pytest suites.
- Deeper docs: `README.md` (full architecture DO/DON'T list), `docs/cli_spec.md` (interface spec + UC index), `docs/uc/` (use cases with related test cases), `docs/cli_e2e_testing_guide.md` (testing practices/troubleshooting).
- No CI, no typecheck config, no pre-commit hooks.
