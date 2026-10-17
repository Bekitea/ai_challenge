# CLI E2E Testing Guide

Глубокое руководство по **CLI e2e**-набору (`core/tests/cli_tests/`):
субпроцессный подход, ground truth, сценарные моки и платформенные нюансы.
Общий обзор всех тестов, политики и команд запуска — в
[`testing.md`](testing.md).

## Overview

CLI e2e-тесты проверяют приложение так, как его видит пользователь:

1. **Субпроцессы, а не вызовы функций** — каждый тест спавнит реальный
   `python main_cli.py` и общается через stdin/stdout.
2. **Ground truth** — проверяется фактическое persisted-состояние
   (`agents.db` + pickle-файлы), а не только подстроки в выводе.
3. **Сценарные моки** — разное поведение LLM на тест через
   `MOCK_LLM_SCENARIO`, без правок кода приложения.
4. **Быстро и параллельно** — `pytest-xdist` (`-n auto`), дешёвый старт
   субпроцесса (ленивые импорты).

Набор запускается в `APPLICATION_MODE=TEST`: мок-провайдер, изолированное
хранилище `test-data-<worker>/` на каждого воркера xdist, чистая БД перед
каждым тестом. Вся эта обвязка — общая, описана в [`testing.md`](testing.md)
и в `core/tests/conftest.py` / `core/tests/cli_tests/conftest.py`.

## Subprocess approach

Тесты взаимодействуют с CLI исключительно через `subprocess.Popen`:

```python
test_input = "1\nHello, how are you?\n/menu\n8\n"

process = subprocess.Popen(
    [sys.executable, "main_cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,  # строки, а не байты — Python сам разберётся с переводами строк
    cwd=str(project_root),
)
stdout, stderr = process.communicate(input=test_input, timeout=30)
```

Предпочитайте общий helper вместо ручного `Popen` — см. контракт
`run_cli_command` ниже.

### Динамические пути

Никогда не хардкодьте абсолютные пути (`/workspace`). Корень проекта
резолвится через `core/tests/e2e_helpers.get_project_root()`
(`core/tests/` → `parents[2]`).

### Переводы строк

`text=True` решает различия Windows (`\r\n`) и Unix (`\n`). Испытания всегда
подают `\n` в `test_input`.

## No business-state fixtures

E2E-тесты **не используют** фикстуры, которые засевают/инжектят состояние
приложения (чаты, профили, сообщения), и не принимают их аргументами.
Единственная допустимая — autouse-фикстура очистки (см. `testing.md`).

```python
# ❌ НЕВЕРНО: фикстура, создающая чат, передана аргументом
def test_something(create_test_chat): ...

# ✅ ВЕРНО: тест сам создаёт состояние через CLI
def test_tc_001_create_chat_default_values(self):
    stdout, _, _ = run_cli_command("1\n\n3\n\n/menu\n8\n")
    assert "Используются настройки по умолчанию." in stdout
```

## Specification traceability

Имена тестов напрямую отображаются на `docs/uc/`:

- класс `TestUC<XXX>_<UseCaseName>`;
- метод `test_tc_<XXX>_<description>`.

Это даёт трассировку «требование → тест», облегчает анализ покрытия и поиск
пробелов. Один файл — один класс тестов (`core/tests/cli_tests/test_ucXXX_*.py`).

## Helper contract (`run_cli_command`)

`core/tests/e2e_helpers.run_cli_command(test_input, timeout=30, env=None, mock=None)`
возвращает `(stdout, stderr, returncode)` и **сам** проверяет перед возвратом:

- `returncode == 0`;
- `stderr == ""`.

Следствия:

- не дублируйте `assert returncode == 0` / `assert "Traceback" not in stderr`;
- неиспользуемые части кортежа отбрасывайте через `_` (Ruff `RUF059`):

  ```python
  stdout, _, _ = run_cli_command(test_input)   # нужен только stdout
  run_cli_command(test_input)                  # результат не проверяется
  ```

- всегда указывайте `timeout` (по умолчанию 30 c) — тест не должен виснуть.

## Ground Truth: проверяйте persisted-состояние

Подстрочные проверки `stdout` хрупки (проходят по неверной причине, ломаются
на `... or ...`). Предпочитайте проверять состояние, которое реально оставил
пользовательский ввод: строки `agents.db` и pickle-файлы `file_storage/`.

Доступ — через `core/tests/ground_truth.py` (сырые `sqlite3` + `pickle`, без
ORM и бизнес-логики, поэтому проверки независимы от кода под тестом). Pickle
`Prompt`/`GlobalMemory`/`TaskMemory` разбираются классами проекта, поэтому
корень проекта должен быть в `sys.path` (это гарантирует общий `conftest.py`).

| Helper | Читает | Типичное применение |
|--------|--------|---------------------|
| `get_agents()` / `get_agent(id)` / `get_agent_by_name(name)` / `get_last_agent()` | таблица `agents` | чат создан, имя, счётчики, превью |
| `get_settings(agent)` | `agents.settings_json` | модель, провайдер, temperature, context window, rerank |
| `get_strategy(agent)` | `agents.strategy_*` | тип и параметры стратегии |
| `get_messages(cid)` / `get_messages_by_name(name)` | `file_storage/<cid>.pkl` | точный диалог: роли, контент, reasoning, tool calls |
| `get_global_memory()` / `get_global_facts()` | `global_memory.pkl` | факты глобальной памяти |
| `get_task_memory(cid)` / `get_task_memory_by_name(name)` | `file_storage/task_memory/<cid>.pkl` | память задачи |
| `get_task_profiles()` / `get_profile_by_name(name)` / `get_profile_facts(id)` / `get_invariants(id)` | `task_profiles`, `task_profile_invariants`, `file_storage/<profile_id>.pkl` | профили, инварианты, факты |
| `get_api_keys()` | `api_keys` | ключ создан/отозван, хранится только хеш |
| `get_knowledge_bases()` / `get_knowledge_base_by_name(name)` / `get_documents(id)` / `get_chunks(doc_id)` / `get_agent_knowledge_bases(agent_id)` | таблицы RAG | жизненный цикл KB/документов/чанков, привязки |

```python
# ❌ Слабо: пройдёт, даже если стратегия не сохранена
assert "SlidingWindowStrategy" in stdout

# ✅ Сильно: стратегия действительно персистирована с введённым окном
from ground_truth import get_agent_by_name, get_strategy

strategy = get_strategy(get_agent_by_name("SlidingWindow Custom"))
assert strategy["strategy_type"] == "SlidingWindowStrategy"
assert strategy["window_size"] == 20
```

Правила:

- проверяйте **точные значения** (контент, счётчики, параметры), а не факт наличия;
- тест, который создаёт/меняет данные, должен читать их обратно через `ground_truth`;
- подстрочные проверки оставляйте для чисто UI-вывода: заголовки меню, приглашения, предупреждения, help;
- сначала дождитесь завершения субпроцесса, потом читайте ground truth.

## Scenario Mocks: поведение LLM на тест

В `TEST` режиме работает `MockLlmProvider` с детерминированным echo по
умолчанию. Чтобы задать конкретные ответы, JSON-payload'ы, токены, tool calls
или ошибки, сценарий передаётся через переменную окружения (тесты запускают
CLI субпроцессом, Python-инъекция невозможна).

**Как устроено:**

- `core/infrastructure/llm/mock_scenario.py` — `MockScenario` и `load_scenario_from_env()` (читает `MOCK_LLM_SCENARIO`);
- `MockLlmProvider` загружает сценарий при создании (без env — прежнее поведение);
- `run_cli_command(input, mock=...)` сериализует сценарий в JSON в `MOCK_LLM_SCENARIO`;
- `e2e_helpers.mock_llm(...)` собирает dict; `core/tests/cli_tests/test_mock_llm_scenarios.py` — эталонный метатест.

**Формат сценария:**

```json
{
  "responses": [
    {"content": "Первый ответ", "reasoning": "r1", "prompt_tokens": 11, "completion_tokens": 2},
    {"content": "Второй ответ", "reasoning": "r2", "prompt_tokens": 12, "completion_tokens": 3},
    {"error": "timeout"},
    {"content": "", "tool_calls": [{"id": "1", "name": "time__now", "arguments": "{}"}]}
  ],
  "default": {"content": "Ответ по умолчанию"},
  "json_object": {"facts": ["Факт X"]}
}
```

- `responses` — по порядку; после исчерпания используется `default`;
- `json_object` — для запросов с `response_format={"type": "json_object"}` (извлечение памяти);
- `error` — `"timeout"` → `LlmTimeoutError`, иначе `RuntimeError`; для проверок graceful degradation.

**Пример:**

```python
from e2e_helpers import _QUICK_CHAT, mock_llm, run_cli_command

# (1) Зафиксировать точные ответы
scenario = mock_llm(responses=[{"content": "ПЕРВЫЙ ОТВЕТ"}, {"content": "ВТОРОЙ ОТВЕТ"}])
run_cli_command(_QUICK_CHAT + "msg1\nmsg2\n/menu\n8\n", mock=scenario)

# (2) Управлять фактами глобальной памяти
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=mock_llm(json_object={"facts": ["Факт X"]}))

# (3) Смоделировать сбой провайдера (приложение покажет [ERROR] и не упадёт)
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=mock_llm(default={"error": "timeout"}))
```

Сценарий env-var driven, поэтому подхватывается везде, где создаётся
`MockLlmProvider` (включая in-process тесты REST API, если `MOCK_LLM_SCENARIO`
выставлен до сборки приложения).

## Common Patterns

### 1. Навигация по меню
```python
stdout, _, _ = run_cli_command("8\n")
assert "--- МЕНЮ ---" in stdout
```

### 2. Быстрое создание чата
```python
from e2e_helpers import _QUICK_CHAT
stdout, _, _ = run_cli_command(_QUICK_CHAT + "/menu\n8\n")
assert "Используются настройки по умолчанию." in stdout
```

### 3. Проверка команды
```python
stdout, _, _ = run_cli_command(_QUICK_CHAT + "/help\n/menu\n8\n")
assert "--- ДОСТУПНЫЕ КОМАНДЫ ---" in stdout
```

### 4. Сценарный мок + ground truth
```python
from e2e_helpers import _QUICK_CHAT, mock_llm, run_cli_command
from ground_truth import get_messages_by_name

scenario = mock_llm(responses=[{"content": "ТОЧНЫЙ ОТВЕТ", "reasoning": "r"}])
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=scenario)

assistants = [m for m in get_messages_by_name("Чат 1") if m["role"] == "assistant"]
assert assistants[0]["content"] == "ТОЧНЫЙ ОТВЕТ"
```

### 5. Несколько операций в одном субпроцессе
Несколько операций в рамках одной сессии выполняйте **в одном субпроцессе**:
это быстрее и избегает Windows-флейков блокировки файлов (`WinError 32`).
Используйте `/menu` для возврата в меню без выхода; `8` — только в самом конце.

```python
test_input = (
    "1\n" + "y\n" + "Chat A\n" + "\n" + "1\n" + "\n" * 6 + "1\n" + "/menu\n"
    + "1\n" + "y\n" + "Chat B\n" + "\n" + "1\n" + "\n" * 6 + "1\n" + "/menu\n"
    + "2\n"  # список чатов
    + "8\n"
)
stdout, _, _ = run_cli_command(test_input)
assert "Chat A" in stdout and "Chat B" in stdout
```

Состояние всё равно проверяйте через ground truth (например,
`get_agent_by_name("Chat A")`).

## Test Performance

Набор упирается в **старт процесса**, а не в логику: каждый тест поднимает
свежий `python main_cli.py`. Что уже сделано:

| Оптимизация | Эффект |
|-------------|--------|
| Ленивый импорт `openai` | `import main_cli` ~2.9s → ~0.5s |
| `clear_screen()` — no-op вне TTY | без спавна `cmd.exe`/`clear` на запуск |
| Параллельный прогон (`-n auto`) + per-worker storage | полный набор ~394s → ~59s |
| Отказ от повторных `returncode`/`stderr` проверок | меньше шума |

Что делать, чтобы тесты оставались быстрыми:

- **Не импортировать тяжёлые модули в тестах.** `openai` импортируется лениво внутри реальных провайдеров; `MockLlmProvider` его не тянет. Не добавляйте top-level `import openai` в модули, загружаемые в TEST.
- **Никакого мокинга на уровне Python** — только субпроцесс + сценарий.
- **Объединяйте шаги в один субпроцесс** (Pattern 5).
- **`-n0` — только для отладки.**
- RAG-тесты делают реальные эмбеддинги через Ollama и **сами** скипаются, если Ollama недоступна (`pytestmark = pytest.mark.skipif(not ollama_available(), ...)`).

```bash
poetry run pytest core/tests/cli_tests -q --durations=20   # профиль медленных
poetry run pytest core/tests/cli_tests/test_uc004_send_message_and_receive_response.py -n0 -v
```

## Windows / cp1251

Консоль Windows по умолчанию `cp1251`, и не-ASCII вывод падает с
`UnicodeEncodeError`. В standalone-скриптах (например,
`core/tests/cli_tests/smoke_test.py`) переключайте stdout на UTF-8:

```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
```

Для маркеров результата в standalone-скриптах используйте ASCII
(`[PASS]` / `[FAIL]`), а не эмодзи.

## Windows: SQLite file locking (`WinError 32`)

**Симптом:**
```
PermissionError: [WinError 32] Процесс не может получить доступ к файлу,
так как этот файл занят другим процессом: '...\test-data\agents.db'
```

**Причина:** SQLite на Windows агрессивно лочит файл БД, и лок не всегда снят
сразу после выхода процесса; autouse-фикстура может пытаться удалить каталог,
пока дескриптор ещё открыт.

**Решение:** фикстура `setup_clean_test_environment` (в
`core/tests/cli_tests/conftest.py`) закрывает своё соединение `DatabaseConnection`
до `yield`, освобождая файл для субпроцесса. Дополнительно каждый воркер
xdist использует приватный `test-data-<worker>/`. Если ошибка сохраняется —
удалите воркер-каталоги и перезапустите:

```powershell
Get-ChildItem -Directory -Filter 'test-data*' | Remove-Item -Recurse -Force
poetry run pytest core/tests/cli_tests -v
```

**Профилактика:** не держите долгоживущие SQLite-соединения в тестах; читайте
ground truth после завершения субпроцесса.

## Troubleshooting

| Issue | Причина / решение |
|-------|-------------------|
| `subprocess.TimeoutExpired` | CLI ждёт ввод/цикл. Проверьте полноту `test_input` и наличие условия выхода; при необходимости увеличьте `timeout` |
| `UnicodeEncodeError` (консоль Windows) | ASCII-маркеры и/или `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| Ожидаемого текста нет в `stdout` | Неверная последовательность ввода или изменение поведения. `print(stdout)` для отладки, сверьте с текущими приглашениями |
| Сценарный мок не действует | `mock` не передан, либо `MOCK_LLM_SCENARIO` — невалидный JSON (игнорируется). `responses` расходуются по порядку — добавьте `default`; для памяти — `json_object` |
| Ground truth пуст/`None` | Чтение до выхода субпроцесса; неверное имя/id; не тот worker-каталог. Читайте после `run_cli_command`, сверяйте с фактическим именем (чаты автоимён `Чат N`) |
| `sqlite3.OperationalError: no such table` | `init_tables` должен идти после установки `APPLICATION_MODE=TEST` |
| Тесты зелёные локально, падают в CI | Разный cwd, отсутствие env, пути. `APPLICATION_MODE=TEST` и per-worker каталог должны быть заданы |
| `[WinError 32]` | См. раздел про SQLite-locking выше |

## См. также

- [`testing.md`](testing.md) — все наборы тестов, политика, команды запуска.
- [`cli_spec.md`](cli_spec.md) — спецификация CLI и индекс use case.
- `docs/uc/` — use case с привязанными тест-кейсами (`TC-xxx`).
