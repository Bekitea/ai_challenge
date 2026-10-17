# Тестирование в проекте

Единая точка входа по тестам: что и где проверяется, как запускать по
отдельности и всё вместе. Глубокие детали CLI e2e-подхода (ground truth,
сценарные моки, субпроцессы, Windows-нюансы) вынесены в
[`cli_e2e_testing_guide.md`](cli_e2e_testing_guide.md).

## Инструменты и конфигурация

- **pytest** + **pytest-xdist**; настройки — в `pyproject.toml`
  (`[tool.pytest.ini_options]`):
  - `addopts = "-n auto"` — полный прогон параллельный по умолчанию;
  - `testpaths = ["core/tests", "llm_gateway/tests", "reranker_service/tests",
    "mcp/tests"]` — что собирается дефолтным `poetry run pytest`.
- **ruff** — линт: `poetry run ruff check --fix`.
- Все тесты, затрагивающие основное приложение, работают в
  `APPLICATION_MODE=TEST` (моки LLM/реранкера, изолированное хранилище
  `test-data-<worker>/`). Это настраивается общим `core/tests/conftest.py`.

## Карта тестов

| Набор | Расположение | Тип | Что проверяет |
| --- | --- | --- | --- |
| CLI e2e | `core/tests/cli_tests/` | E2E (subprocess, по спецификации) | Пользовательские сценарии CLI: одна use case — один файл, `TestUCxxx` / `test_tc_xxx` |
| Core (unit/integration) | `core/tests/core_tests/` | Unit / integration | Логика, которую нецелесообразно проверять через CLI e2e (домен, провайдеры, RAG, промпт-билдер, память) |
| REST API | `core/tests/api_tests/` | Integration (in-process `TestClient`) | Эндпоинты API и авторизация по API-ключу |
| LLM Gateway | `llm_gateway/tests/` | Unit / integration (in-process) | Очередь, воркер, проксирование, 503/504/499 |
| Reranker | `reranker_service/tests/` | Unit / integration (in-process) | HTTP-контракт `POST /rerank`, `/health` |
| MCP-серверы | `mcp/tests/` | Integration (spawn subprocess) | Инструменты `time_mcp` и `open_alex_mcp` |

Плюс вспомогательные элементы, не являющиеся тестами:

- `core/tests/cli_tests/smoke_test.py` — standalone smoke-обёртка над
  несколькими ключевыми e2e-кейсами (запускается напрямую, не через pytest);
- `scripts/check_sqlite_vec.py` — **скрипт** проверки собранного расширения
  `sqlite-vec` (см. раздел ниже).

## Общая инфраструктура

- `core/tests/conftest.py` — общая настройка: `APPLICATION_MODE=TEST`,
  изоляция `AI_CHAT_TEST_DATA_DIR` по воркерам xdist, `sys.path`, session-хуки
  очистки «осиротевших» `test-data*`.
- `core/tests/e2e_helpers.py` — `run_cli_command` (спавн `main_cli.py`),
  `mock_llm` (сценарные моки через `MOCK_LLM_SCENARIO`), работа с тестовым
  хранилищем, `get_project_root`.
- `core/tests/ground_truth.py` — read-only доступ к persisted-состоянию
  (`agents.db` + pickle-файлы): чаты, настройки, история, память, профили, RAG.
- Специфичные фикстуры живут рядом с наборами: `core/tests/cli_tests/conftest.py`
  (autouse-очистка + инициализация схемы БД) и
  `core/tests/api_tests/conftest.py` (`app`, `client`, `anon_client`).

## Политика: когда писать unit/integration-тесты

В проекте **обычно не пишут модульные и интеграционные тесты** — основной
способ проверки это CLI e2e по спецификации (ground truth + сценарные моки),
потому что он проверяет систему целиком как её видит пользователь.

Исключение: если логику **очень сложно или невозможно** проверить через e2e
(например, fail-fast домена, трансляция параметров в провайдер, пороги RAG,
сериализация стратегий, разбор очереди gateway), то модульные/интеграционные
тесты **нужно** писать. Такие тесты живут в `core/tests/core_tests/` (для
основного приложения) или рядом с сервисом (`llm_gateway/tests/`,
`reranker_service/tests/`). Если появляется e2e-покрытие, дублирующий
unit-тест не добавляем.

## Запуск

Всё через Poetry, из корня проекта.

```bash
# Полный прогон (параллельно, все testpaths)
poetry run pytest

# По наборам
poetry run pytest core/tests/cli_tests        # CLI e2e
poetry run pytest core/tests/core_tests       # core unit/integration
poetry run pytest core/tests/api_tests        # REST API
poetry run pytest llm_gateway/tests           # LLM Gateway
poetry run pytest reranker_service/tests      # Reranker
poetry run pytest mcp/tests                   # MCP-серверы

# Последовательно (отладка одного кейса)
poetry run pytest core/tests/cli_tests -n0 -v

# Конкретный Use Case / тест
poetry run pytest core/tests/cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings -n0 -v
poetry run pytest core/tests/cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings::test_tc_001_quick_chat_creation_with_defaults -n0 -v

# Smoke (standalone-обёртка над ключевыми e2e)
poetry run python core/tests/cli_tests/smoke_test.py
```

По умолчанию CLI e2e-кейсы требуют только mock-провайдера и не нуждаются в
API-ключах. Часть RAG-кейсов и сетевые MCP-кейсы сами делают `pytest.skip`,
если недоступны внешние зависимости (Ollama, сеть).

## Скрипт проверки sqlite-vec

`scripts/check_sqlite_vec.py` — **не тест**, а ручная проверка вендоренного
расширения `sqlite-vec` (`vec0.so`/`vec0.dll`): загрузка, версия, векторный
поиск.

```bash
poetry run python scripts/check_sqlite_vec.py
```

## Как добавить тест

1. Для пользовательского сценария: добавьте use case в `docs/uc/`, заведите
   e2e-файл `core/tests/cli_tests/test_ucXXX_*.py` с классом `TestUCxxx_...` и
   методами `test_tc_XXX_...`, проверяйте состояние через `ground_truth.py`.
2. Для сложной/непроверяемой через CLI логики: добавьте тест в
   `core/tests/core_tests/`.
3. Для отдельного сервиса (gateway/reranker/MCP): тест рядом с сервисом.

## Дополнительно

- [`cli_e2e_testing_guide.md`](cli_e2e_testing_guide.md) — детали e2e:
  ground truth, сценарные моки, субпроцессный паттерн, Windows/cp1251,
  troubleshooting, SQLite-локи.
- [`cli_spec.md`](cli_spec.md) — спецификация интерфейса и индекс use case.
- `docs/uc/` — use case с привязанными тест-кейсами (`TC-xxx`).
