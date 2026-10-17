# CLI Testing Guide

## Overview

This guide documents the experience and best practices for testing CLI applications in this project, particularly focusing on cross-platform compatibility between Linux (CI/development environment) and Windows (local development).

It covers three ideas that are central to the current test suite:

1. **Ground truth first** — verify the persisted state (SQLite + pickle files), not just substrings in CLI output.
2. **Scenario mocks** — inject different LLM behaviour per test through an environment variable.
3. **Fast by default** — the suite runs in parallel (`pytest-xdist`) and keeps subprocess startup cheap.

## Test Isolation and Data Management

### Test Mode and Data Isolation

**CRITICAL:** All automated tests MUST run in **TEST MODE** to ensure complete isolation from production data.

**Mechanism:** The application uses the `APPLICATION_MODE` environment variable to determine data storage locations (see `config.py`):

| Mode | Environment Variable | Storage root | Database | File storage |
|------|---------------------|--------------|----------|--------------|
| **PROD** (default) | `APPLICATION_MODE=PROD` or not set | `./data/` | `./data/agents.db` | `./data/file_storage/` |
| **LOCAL** | `APPLICATION_MODE=LOCAL` | `./local-data/` | `./local-data/agents.db` | `./local-data/file_storage/` |
| **TEST** | `APPLICATION_MODE=TEST` | `./test-data[-<worker>]/` | `agents.db` | `file_storage/` |

The storage root is split into:

| Artifact | Path (relative to the storage root) |
|----------|-------------------------------------|
| Chat metadata, settings, strategies, token counters, task profiles, invariants, API keys, RAG tables | `agents.db` (SQLite) |
| Per-chat message history (pickled `Prompt` objects) | `file_storage/<conversation_id>.pkl` |
| Per-chat task memory | `file_storage/task_memory/<conversation_id>.pkl` |
| Task profile facts | `file_storage/<profile_id>.pkl` |
| Global memory | `global_memory.pkl` |

**How It Works:**

1. **Before each test:** the test framework sets `APPLICATION_MODE=TEST` in the subprocess environment
2. **CLI startup:** the application reads `APPLICATION_MODE` and configures paths accordingly
3. **Test execution:** all data operations use the isolated storage root
4. **Before each test:** the per-worker storage directory is removed and recreated (`clean_test_data()`)

**Benefits:**

- ✅ Production data in `./data/` is never touched by tests
- ✅ Each test starts with a clean slate (no residual state)
- ✅ Tests run in parallel without conflicts (see the next section)
- ✅ Failed tests leave artifacts for debugging

### Cleanup Lifecycle

`test-data*` directories are managed by session/test hooks in `cli_tests/conftest.py`
(and the same hooks in `api_tests/conftest.py`):

| Moment | Action |
|--------|--------|
| Session start | remove **orphaned** `test-data*` dirs from previous runs (only those whose mtime is older than the current session, so active worker dirs are untouched) |
| Before each test | `clean_test_data()` removes and recreates the current worker's dir, then the DB schema is initialized |
| Session end, exit code `0` | remove **all** `test-data*` dirs |
| Session end, exit code `!= 0` | keep the dirs so you can inspect the failure |

On the xdist controller the aggregated exit status is used, so a failing worker's
directory is not deleted because of a green run elsewhere. Orphan cleanup runs only
on the controller (no `PYTEST_XDIST_WORKER`) to avoid racing workers.

`test-data*` (and `local-data*`) are listed in `.gitignore`, so leftover debug dirs
never show up as untracked files.

### Parallel Runs: Per-Worker Storage

The full suite runs in parallel by default (`pytest-xdist`, configured as `-n auto` in `pyproject.toml [tool.pytest.ini_options]`). To keep parallel tests isolated, each xdist worker gets **its own storage directory**:

- `cli_tests/e2e_helpers.py` resolves the directory name from `PYTEST_XDIST_WORKER`:
  `test-data-<worker>` when running under xdist, otherwise `test-data`.
- That relative path is exported as `AI_CHAT_TEST_DATA_DIR`, which `config.py` reads in `TEST` mode. The same variable is passed to every CLI subprocess.
- In a worker the value is **overwritten** (not `setdefault`): the controller exports `AI_CHAT_TEST_DATA_DIR=./test-data`, and workers inherit it, so without the override a worker's own fixture would write to the shared `test-data` while its subprocess wrote to `test-data-<worker>`.
- `clean_test_data()` / `get_test_data_path()` are worker-aware, and `cli_tests/ground_truth.py` reads from the same directory.

You can override the directory manually (useful when debugging a single case serially):

```bash
AI_CHAT_TEST_DATA_DIR=./test-data-debug poetry run pytest cli_tests/ -n0 -v
```

### Test Setup And Teardown: The Module-Level autouse Fixture

Isolation is provided by a single module-level `@pytest.fixture(autouse=True)` in `cli_tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def setup_clean_test_environment():
    """Automatically clean test data and initialize DB before each test."""
    clean_test_data()  # remove + recreate the per-worker test-data-<worker>/ dir

    db = DatabaseConnection(connect_args={"check_same_thread": False, "timeout": 30})
    db.init_tables(Base.metadata)   # create schema in the isolated test DB
    db.close()                      # release the file handle for the subprocess (Windows)

    yield
```

What this fixture does NOT do — and what the "No Business-State Fixtures" section below is actually about:

- It does not inject any state into tests as a parameter; no test signature depends on it.
- It does not create chats, profiles or messages — every test builds its own state through CLI stdin interaction inside a subprocess.
- It does not mock anything at the Python level; it only prepares the empty isolated `test-data-<worker>/` storage. (Per-test LLM behaviour is controlled via the `MOCK_LLM_SCENARIO` environment variable, not by monkeypatching.)

In other words, the ban applies to **business-state fixtures** (fixtures that seed application data or are passed as test arguments).

**Example Test:**

```python
from e2e_helpers import _QUICK_CHAT, run_cli_command


class TestUC001_CreateChatWithAllSettings:

    def test_tc_001_quick_chat_creation_with_defaults(self):
        # The autouse fixture already ran: per-worker test-data is clean and the DB is initialized

        # _QUICK_CHAT: "1" (New Chat) -> Enter (configure prompt, default "n")
        #              -> "3" (model is required, no default) -> Enter (reasoning effort)
        test_input = _QUICK_CHAT + "/menu\n8\n"  # back to menu, then exit

        run_cli_command(test_input)

        # Ground truth: the chat is persisted with a default name
        from ground_truth import get_last_agent

        assert get_last_agent()["name"].startswith("Чат")
```

### Manual Testing with Different Modes

**Test Mode (Manual):**
```bash
# Linux/macOS
APPLICATION_MODE=TEST python main_cli.py

# Windows PowerShell
$env:APPLICATION_MODE="TEST"; python main_cli.py

# Windows CMD
set APPLICATION_MODE=TEST && python main_cli.py
```

**Production Mode:**
```bash
# Uses ./data/ directory - requires API keys for real LLM calls
python main_cli.py
```

## Key Challenges

### 1. Working Directory Issues

**Problem:** Hardcoded absolute paths like `/workspace` cause failures on Windows and other environments.

**Solution:** Use dynamic path resolution based on the script's location:

```python
from pathlib import Path

# Get the directory where the test script is located
script_dir = Path(__file__).parent.absolute()

# Get the project root (parent of the test directory)
project_root = script_dir.parent

# Use the resolved path for subprocess calls
process = subprocess.Popen(
    [sys.executable, "main_cli.py"],
    # ... other parameters ...
    cwd=str(project_root),
)
```

This approach ensures tests work regardless of:

- The actual location of the project on disk
- The operating system (Windows, Linux, macOS)
- Whether running in CI or locally

### 2. Interactive Input Simulation

**Challenge:** CLI applications require user input, but automated tests need predefined inputs.

**Solution:** Use `subprocess.Popen` with `stdin=subprocess.PIPE`:

```python
test_input = "1\nHello, how are you?\n0\n"

process = subprocess.Popen(
    [sys.executable, "main_cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,  # Important: handle strings instead of bytes
    cwd=str(project_root),
    env={**os.environ, "APPLICATION_MODE": "TEST"},  # Critical for isolation!
)

stdout, stderr = process.communicate(input=test_input, timeout=30)
```

### 3. Cross-Platform Line Endings

**Note:** While Python's `text=True` mode handles most line ending conversions automatically, be aware that:

- Windows uses `\r\n`
- Unix/Linux uses `\n`

Using `text=True` in subprocess calls lets Python handle these differences.

## Test Structure

### Basic Test Template

Prefer reusing the shared helper instead of hand-rolling `subprocess.Popen`. `run_cli_command` resolves paths, sets `APPLICATION_MODE=TEST` and the per-worker storage dir, and enforces `returncode == 0` + empty `stderr`:

```python
"""E2E tests: TestUCxxx_..."""

from e2e_helpers import run_cli_command


class TestUCxxx_Example:

    def test_tc_xxx_example(self):
        test_input = "1\n\n3\n\n/menu\n8\n"  # model + reasoning are required
        stdout, _, _ = run_cli_command(test_input)
        assert "--- МЕНЮ ---" in stdout
```

The standalone smoke test (`cli_tests/smoke_test.py`) is a thin wrapper that runs a few critical pytest cases:

```bash
poetry run python cli_tests/smoke_test.py
```

> **Windows note:** keep console output ASCII and/or call
> `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the top of standalone
> scripts. Emoji markers crash under the default `cp1251` console codec
> (`UnicodeEncodeError`). Use `[OK]` / `[PASS]` / `[FAIL]` instead of ✅ / ❌.

## Best Practices

### 1. Always Use Dynamic Paths

Never hardcode absolute paths. Always resolve them relative to the test script location.

### 2. Set Reasonable Timeouts

Always specify a `timeout` parameter in `communicate()` to prevent hanging tests.

### 3. Capture Both stdout and stderr

Some applications write warnings or errors to stderr. `run_cli_command` captures both streams and enforces the success invariant itself: `returncode == 0` and empty `stderr`. Tests therefore only assert on `stdout` and drop the unused parts of the tuple with `_`.

### 4. Use Descriptive Test Names

Name test files descriptively: `smoke_test.py`, `test_chat_flow.py`, etc.

### 5. Document Test Scenarios

Include comments explaining what each test scenario validates.

### 6. Control Mock Behaviour With Scenarios

In TEST mode the application uses `MockLlmProvider`. Instead of asserting the single hardcoded echo answer, pass a per-test scenario (see [Scenario Mocks](#scenario-mocks-llm-behaviour-per-test)). This lets a test pin exact response content, reasoning, token counts, JSON payloads (memory extraction), tool calls, or simulate provider errors — without touching application code.

### 7. Use APPLICATION_MODE Environment Variable

The application uses the `APPLICATION_MODE` environment variable to control both the LLM provider and data storage location:

```python
# Always set APPLICATION_MODE=TEST in automated tests
env = os.environ.copy()
env["APPLICATION_MODE"] = "TEST"

process = subprocess.Popen(
    [sys.executable, "main_cli.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=str(project_root),
    env=env,  # Critical for isolation!
)
```

This ensures:

- Tests always run with the Mock provider (no API keys required)
- Tests use an isolated per-worker storage dir `test-data-<worker>/` (production data safe)
- Each test starts with a clean database state
- Clear separation between test and production scenarios

## Running Tests

### Automated Tests Must Use Test Mode

**IMPORTANT:** All automated test scripts **MUST** set `APPLICATION_MODE=TEST` environment variable.

This ensures:

- Tests run without requiring real API keys
- Tests use the `MockLlmProvider` for predictable, fast, and isolated execution
- Tests use an isolated per-worker storage dir (production data in `./data/` is never touched)
- No accidental costs or external dependencies during testing
- Each test starts with a clean database state

### From Any Location

```bash
# Run the smoke test (sets APPLICATION_MODE=TEST internally)
poetry run python cli_tests/smoke_test.py
```

### Running E2E Tests with pytest

The project includes pytest-based E2E tests that emulate real user interaction via subprocess calls. These tests:

- Use `subprocess.Popen` to spawn actual CLI processes (no mocking at Python level)
- Send input via stdin (simulating keyboard input)
- Capture stdout/stderr (simulating terminal output) and assert `returncode == 0` plus empty `stderr` via `run_cli_command`
- Set `APPLICATION_MODE=TEST` for complete isolation
- Use only the autouse **cleanup** fixture (no business-state fixtures) so each test is self-contained
- Verify persisted state via `cli_tests/ground_truth.py`
- Directly map to test cases from the use case files under `docs/uc/`

The full suite runs **in parallel by default** (`-n auto` in `pyproject.toml`) and takes about a minute. Every worker gets its own `test-data-<worker>/` directory, so there are no collisions.

```bash
# Run all E2E tests (parallel by default; APPLICATION_MODE=TEST is set automatically)
poetry run pytest cli_tests/ -v

# Force a serial run (e.g. when debugging a single case)
poetry run pytest cli_tests/ -n0 -v

# Run specific test class (Use Case)
poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings -n0 -v

# Run specific test
poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings::test_tc_001_quick_chat_creation_with_defaults -n0 -v
```

**Note for Windows Users:** If you encounter `[WinError 32] Process cannot access file` errors, see the "Windows-Specific: SQLite File Locking Issue" section below for solutions.

### Test Organization and Naming Convention

**IMPORTANT:** All E2E tests follow a strict naming convention for direct traceability to the specification:

- **Test classes** are named after Use Cases: `TestUC001_CreateChatWithAllSettings`
- **Test methods** are named after Test Cases: `test_tc_001_create_chat_default_values`
- Format: `test_tc_XXX_<description>` where `XXX` is the test case number from the corresponding use case file in `docs/uc/`

This ensures:
1. Easy mapping between specification and implementation
2. Clear coverage tracking
3. Simple identification of missing tests

### Why This Approach?

The existing smoke test (`smoke_test.py`) and pytest E2E tests intentionally avoid business-state fixtures and direct function calls because:

1. **Real User Simulation**: Tests interact with the CLI exactly as a real user would - through stdin/stdout
2. **Cross-Platform Compatibility**: Subprocess approach works identically on Windows, Linux, and macOS
3. **No Hidden State**: Each test is completely independent, avoiding fixture-related side effects
4. **True Integration Testing**: Tests verify the entire stack - from CLI parsing to database operations
5. **Specification Traceability**: Direct mapping to the `docs/uc/` use case files ensures complete coverage

```python
# Example test structure (from a per-class test file)
class TestUC001_CreateChatWithAllSettings:
    """Use Case UC-001: Create New Chat with All Settings"""

    def test_tc_001_create_chat_default_values(self):
        """
        TC-001: Quick Chat Creation With Defaults
        """
        test_input = (
            "1\n"           # Новый чат
            "\n"            # Configure prompt → quick path (default "n")
            "3\n"           # Model selection (required; no default model)
            "\n"            # Reasoning effort (default "none")
            "/menu\n"       # Leave the chat loop
            "8\n"           # Exit the application
        )
        stdout, _, _ = run_cli_command(test_input)

        assert "Используются настройки по умолчанию." in stdout
        # Ground truth: the chat is persisted with a default name
        from ground_truth import get_last_agent
        assert get_last_agent()["name"].startswith("Чат")
```

### Running Tests in Different Modes

**Test Mode (Default for Automated Tests):**
```bash
# APPLICATION_MODE=TEST is set automatically in tests
poetry run pytest cli_tests/ -v
```

**Smoke Test (comprehensive scenario):**
```bash
# Runs multiple test cases via pytest to verify critical paths:
# - TC-014: Send Multiple Messages (mock provider + history)
# - TC-032: Settings Change With Confirmation (storage read/write)
# - TC-029: Create Branch And Switch (branching + navigation)
poetry run python cli_tests/smoke_test.py
```

**Manual Exploration:**
```bash
# Run CLI manually in test mode (Mock provider, ./test-data/)
# Linux/macOS:
APPLICATION_MODE=TEST python main_cli.py

# Windows PowerShell:
$env:APPLICATION_MODE="TEST"; python main_cli.py

# Windows CMD:
set APPLICATION_MODE=TEST && python main_cli.py

# Run CLI manually in production mode (requires API keys, ./data/)
export YANDEX_CLOUD_API_KEY="your_key"
export YANDEX_CLOUD_FOLDER_ID="your_folder"
python main_cli.py
```

## Core Principles for CLI E2E Testing

### 1. No Business-State Fixtures

**Rule:** E2E tests MUST NOT use fixtures that seed or inject application state (chats, profiles, messages) or that are passed as test arguments. The only allowed fixture is the module-level **autouse cleanup** fixture in `conftest.py`.

**Rationale:**
- Each test must be completely self-contained
- Avoids hidden state between tests
- Ensures tests can run in any order and in parallel
- Maximizes realism (a real user has no "fixtures")

**Example:**
```python
# ❌ WRONG: state-seeding fixture passed as an argument
@pytest.fixture
def create_test_chat():
    # Creates chat in database
    yield chat
    # Cleanup

def test_something(create_test_chat):
    ...

# ✅ CORRECT: self-contained test (only autouse cleanup runs)
def test_tc_001_create_chat_default_values(self):
    """Test creates its own state via CLI interaction."""
    test_input = "1\n\n3\n\n/menu\n8\n"
    stdout, _, _ = run_cli_command(test_input)
    assert "Используются настройки по умолчанию." in stdout
```

### 2. Subprocess-Only Interaction

**Rule:** Tests MUST interact with CLI exclusively through `subprocess.Popen`.

**Rationale:**
- Simulates real user behavior (keyboard input → terminal output)
- Cross-platform compatibility (Windows/Linux/macOS)
- Tests entire stack (CLI parser → business logic → database)
- No mocking at Python level

**Example:**
```python
# ❌ WRONG: Direct function calls
from main_cli import create_chat
chat = create_chat(name="Test")

# ✅ CORRECT: Subprocess interaction
test_input = "1\nTest\n...\n"
stdout, _, _ = run_cli_command(test_input)
```

### 3. Dynamic Path Resolution

**Rule:** NEVER hardcode absolute paths like `/workspace`.

**Rationale:**
- Works on any machine (Windows, Linux, macOS)
- Works in CI/CD and local development
- Works regardless of project location

**Example:**
```python
# ❌ WRONG: Hardcoded path
project_root = Path("/workspace")

# ✅ CORRECT: Dynamic resolution
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
```

### 4. Specification Traceability

**Rule:** Test names MUST directly map to test cases in the use case files under `docs/uc/`.

**Format:**
- Class name: `TestUC<XXX>_<UseCaseName>`
- Method name: `test_tc_<XXX>_<description>`

**Rationale:**
- Easy coverage tracking
- Clear requirement-to-test mapping
- Simple gap analysis

**Example:**
```python
class TestUC001_CreateChatWithAllSettings:
    """Covers UC-001 from specification."""

    def test_tc_001_create_chat_default_values(self):
        """Directly maps to TC-001 in docs/uc/uc-001-create-new-chat-with-all-settings.md."""
        ...

    def test_tc_002_create_chat_custom_settings(self):
        """Directly maps to TC-002 in docs/uc/uc-001-create-new-chat-with-all-settings.md."""
        ...
```

### 5. Timeout Enforcement

**Rule:** ALL subprocess calls MUST specify a `timeout` parameter.

**Rationale:**
- Prevents hanging tests
- Catches infinite loops
- Ensures CI/CD reliability

**Example:**
```python
# ❌ WRONG: No timeout
stdout, stderr = process.communicate(input=test_input)

# ✅ CORRECT: Explicit timeout
stdout, stderr = process.communicate(input=test_input, timeout=30)
```

### 6. Test Mode Requirement

**Rule:** Automated tests MUST set `APPLICATION_MODE=TEST` environment variable.

**Rationale:**
- No API keys required
- Fast execution (mock responses)
- Predictable behavior
- No external dependencies
- Isolated data storage (`test-data-<worker>/` vs `./data/`)
- Clean state for each test

**Example:**
```python
# ❌ WRONG: Production mode (uses ./data/)
env = os.environ.copy()
process = subprocess.Popen([sys.executable, "main_cli.py"], ..., env=env)

# ✅ CORRECT: Test mode (uses test-data-<worker>/)
env = os.environ.copy()
env["APPLICATION_MODE"] = "TEST"
process = subprocess.Popen([sys.executable, "main_cli.py"], ..., env=env)
```

### 7. Complete Output Capture

**Rule:** ALWAYS capture both `stdout` AND `stderr`, and treat a non-zero exit code or non-empty `stderr` as a test failure.

**Rationale:**
- Complete debugging information
- Catch warnings and errors
- Verify correct output streams
- A clean `stderr` on success proves the app did not leak errors/warnings

**Example:**
```python
# ✅ `run_cli_command` already captures both streams and asserts
# returncode == 0 plus an empty stderr.
# ❌ WRONG: only stdout (raw subprocess, no stderr captured)
stdout = process.stdout.read()

# ✅ CORRECT: helper captures both and enforces the invariant
stdout, _, _ = run_cli_command(test_input)
```

### Helper Contract (`run_cli_command`)

`e2e_helpers.run_cli_command(test_input, timeout=30)` returns `(stdout, stderr, returncode)` and, before returning, asserts:

- `returncode == 0`
- `stderr == ""`

Consequences for tests:

- Do **not** repeat `assert returncode == 0` or `assert "Traceback" not in stderr` — the helper already guarantees it (with a detailed failure message containing `stdout`/`stderr`).
- Unused parts of the tuple **must** be discarded with `_` to keep Ruff (`RUF059`) clean:
  ```python
  stdout, _, _ = run_cli_command(test_input)   # only stdout needed
  _, stderr, _ = run_cli_command(test_input)   # only stderr needed
  run_cli_command(test_input)                  # result not inspected at all
  ```

## Ground Truth: Verify Persisted State

Substring checks in `stdout` are brittle: they can pass for the wrong reason (e.g. a name echoed back in a prompt) and a single fallback like `assert "A" in stdout or "B" in stdout` makes a test nearly always green. **Prefer asserting the state that the user input actually produced** — rows in `agents.db` and pickle files under `file_storage/`.

The accessors live in `cli_tests/ground_truth.py`. They read with raw `sqlite3` + `pickle` (no ORM, no business logic), so they stay independent of the application code under test. Pickled `Prompt`/`GlobalMemory`/`TaskMemory` objects are unpickled using the project classes, which is why the test process must run with the project root on `sys.path` (the autouse `conftest.py` guarantees this).

Where each fact lives (relative to the worker storage root):

| Helper | Reads | Typical use |
|--------|-------|-------------|
| `get_agents()` / `get_agent(id)` / `get_agent_by_name(name)` / `get_last_agent()` | `agents` table | chat created, name, message count, preview, token counters |
| `get_settings(agent)` | `agents.settings_json` | model, provider, temperature, top_p, context window, rerank flag |
| `get_strategy(agent)` | `agents.strategy_*` | strategy type + params (`window_size`, `non_compressible_count`, `buffer_size`, `summary`) |
| `get_messages(conversation_id)` / `get_messages_by_name(name)` | `file_storage/<cid>.pkl` | exact dialogue: roles, content, reasoning, tool calls, `is_remembered` |
| `get_global_memory()` / `get_global_facts()` | `global_memory.pkl` | facts extracted into global memory |
| `get_task_memory(cid)` / `get_task_memory_by_name(name)` | `file_storage/task_memory/<cid>.pkl` | per-chat task memory (goal/constraints/terms) |
| `get_task_profiles()` / `get_profile_by_name(name)` / `get_profile_facts(id)` / `get_invariants(id)` | `task_profiles`, `task_profile_invariants`, `file_storage/<profile_id>.pkl` | profiles and their invariants/facts |
| `get_api_keys()` | `api_keys` table | key created/removed, prefix, that only a hash is stored |
| `get_knowledge_bases()` / `get_knowledge_base_by_name(name)` / `get_documents(id)` / `get_chunks(doc_id)` / `get_agent_knowledge_bases(agent_id)` | RAG tables | KB/document/chunk lifecycle, attachments |

Example — replacing a weak output assertion with ground truth:

```python
# ❌ Weak: passes even if the strategy was never saved
assert "SlidingWindowStrategy" in stdout

# ✅ Strong: the strategy is actually persisted with the entered window
from ground_truth import get_agent_by_name, get_strategy

strategy = get_strategy(get_agent_by_name("SlidingWindow Custom"))
assert strategy["strategy_type"] == "SlidingWindowStrategy"
assert strategy["window_size"] == 20
```

Guidelines:

- Assert **exact values** (content, counts, params) rather than presence.
- A test that creates/modifies data should read it back via `ground_truth`.
- Keep substring checks for genuinely UI-only output: menu headers, prompts, warnings, help text.
- Run the CLI subprocess first, then read ground truth (state is flushed to disk when the process exits).

## Scenario Mocks: LLM Behaviour Per Test

In `TEST` mode the app uses `MockLlmProvider`. Its default behaviour is a deterministic echo, which is too coarse when a test needs specific answers, JSON payloads, token counts, tool calls, or errors. The provider therefore accepts a **scenario** passed through an environment variable (tests run the CLI as a subprocess, so Python-level injection is not possible).

**How it is wired:**

- `mock_llm.py` defines `MockScenario` and `load_scenario_from_env()` (reads `MOCK_LLM_SCENARIO`).
- `MockLlmProvider` loads the scenario at construction (no env → previous default behaviour, fully backward compatible).
- `e2e_helpers.run_cli_command(input, mock=...)` serialises the scenario to JSON into `MOCK_LLM_SCENARIO`.
- `e2e_helpers.mock_llm(...)` builds the dict; `cli_tests/test_mock_llm_scenarios.py` is the reference example.

**Scenario format:**

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

- `responses` — consumed **in order**; when exhausted, `default` is used.
- `json_object` — returned for requests with `response_format={"type": "json_object"}` (memory / task-memory extraction). A bare object is serialised to a JSON string automatically.
- `error` — `"timeout"` raises `LlmTimeoutError`; any other value raises `RuntimeError("mock llm error: ...")`. Use it to test graceful degradation.

**Usage:**

```python
from e2e_helpers import _QUICK_CHAT, mock_llm, run_cli_command

# (1) Pin exact answers
scenario = mock_llm(responses=[{"content": "ПЕРВЫЙ ОТВЕТ"}, {"content": "ВТОРОЙ ОТВЕТ"}])
run_cli_command(_QUICK_CHAT + "msg1\nmsg2\n/menu\n8\n", mock=scenario)

# (2) Control extracted global-memory facts
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=mock_llm(json_object={"facts": ["Факт X"]}))

# (3) Simulate a provider failure (app must show [ERROR] and not crash)
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=mock_llm(default={"error": "timeout"}))
```

Because the scenario is env-var driven, it is picked up by `MockLlmProvider` wherever it is constructed — including the in-process REST API tests, as long as `MOCK_LLM_SCENARIO` is set before the app is built. Scenarios are particularly useful for memory extraction (`json_object`), task memory, and error-path tests, where the default echo cannot produce the required shape.

## Test Performance

The suite is dominated by **process startup**, not by application logic: every test spawns a fresh `python main_cli.py`, and each spawn used to import the whole dependency tree. Measured before/after on a dev machine:

| Optimisation | Effect |
|--------------|--------|
| Lazy-import the `openai` SDK | `import main_cli` ~2.9s → ~0.5s (`openai` alone was ~1.87s) |
| `clear_screen()` no-op when `stdout` is not a TTY | avoids spawning `cmd.exe`/`clear` per run |
| Parallel run (`pytest-xdist`, `-n auto`) + per-worker storage | full suite **~394s → ~59s** |
| Not re-asserting `returncode`/`stderr` (helper does it) | less noise, fewer redundant checks |

How to keep new tests fast:

- **Do not re-import heavy modules in tests.** `openai` is imported lazily inside the real providers (`YandexCloudLlmProvider` / `OllamaLlmProvider`); `MockLlmProvider` and `rag` embedding calls do not pull it in. Do not add a top-level `import openai` to application modules that TEST mode loads.
- **Never mock at the Python level by importing the app** in a test — use the subprocess + scenario approach.
- **Batch related steps into one subprocess** (see [Pattern 7](#pattern-7-multiple-operations-in-single-subprocess)) instead of many short runs.
- **Keep tests serial (`-n0`) only for debugging.** The default parallel run gives each worker a private `test-data-<worker>/`, so no manual coordination is needed.
- RAG tests do real embeddings through Ollama and are automatically skipped when Ollama is unavailable (`pytestmark = pytest.mark.skipif(not ollama_available(), ...)`), so they neither fail nor slow down a machine without it.

```bash
# Normal (parallel) run
poetry run pytest cli_tests/

# Profile the slowest tests
poetry run pytest cli_tests/ -q --durations=20

# Debug one case serially
poetry run pytest cli_tests/test_uc004_send_message_and_receive_response.py -n0 -v
```


## Test Case Design Guidelines

### Structuring Test Input

Build input strings that mirror real user keystrokes:

```python
test_input = (
    "1\n"           # Menu option: New Chat
    "y\n"           # Configure manually
    "My Chat\n"     # Chat name
    "You are helpful\n"  # System prompt
    "1\n"           # Model selection (required; no default model)
    "0.7\n"         # Temperature
    "\n"            # Top P (default)
    "\n"            # Top K (default)
    "\n"            # Max tokens (default)
    "\n"            # Reasoning effort (default)
    "\n"            # Context window (default)
    "1\n"           # Strategy: DefaultStrategy
    "/menu\n"       # Leave the chat loop
    "8\n"           # Exit the application
)
```

### Assertion Strategy

Prefer **ground truth** (persisted state) over matching substrings in CLI output. Output checks are acceptable for pure UI messages that are not persisted (menu headers, prompts, warnings), but a test that changes data should assert the data.

The exit code and empty `stderr` are enforced by `run_cli_command`, so tests do not assert them explicitly:

```python
# ✅ Get stdout (exit code / stderr are checked by the helper)
stdout, _, _ = run_cli_command(test_input)

# ✅ UI-only assertions (nothing persisted to check)
assert "--- МЕНЮ ---" in stdout
assert "Неверный выбор, попробуйте снова." in stdout

# ✅ Strong assertions: read the persisted state
from ground_truth import get_agent_by_name, get_settings

settings = get_settings(get_agent_by_name("My Chat"))
assert settings["model_id"] == "aliceai-llm-flash/latest"
assert settings["temperature"] == 0.7

# ❌ Avoid: substring checks that can match unrelated output, or `... or ...` fallbacks
assert "1. Новый чат" in stdout or "МЕНЮ" in stdout  # meaningless — passes on almost anything
# ❌ Avoid: assert returncode == 0 / "Traceback" not in stderr (guaranteed by the helper)
```

See [Ground Truth](#ground-truth-verify-persisted-state) for the full helper API.

### Handling Sequential Dependencies

When tests need prior state, create it within the test:

```python
def test_tc_013_return_to_chat_with_active_chat(self):
    """TC-013: Must have active chat first."""
    # Step 1: Create chat
    # Step 2: Send message (makes it active)
    # Step 3: Go to menu
    # Step 4: Use "Return to chat"
    test_input = (
        "1\n"           # New chat
        "y\n"           # Configure the chat manually
        "Test\n"        # Name
        "\n"            # Skip system prompt
        "1\n"           # Model (required; no default model)
        "\n\n\n\n\n\n"  # Defaults: temp/top_p/top_k/max_tokens/reasoning/context
        "1\n"           # DefaultStrategy
        "Hello\n"       # Send message
        "/menu\n"       # Go to menu
        "5\n"           # Return to chat
        "/menu\n"       # Go to menu again
        "8\n"           # Exit
    )
    stdout, _, _ = run_cli_command(test_input)
    assert "[OK] Возврат в чат: Test" in stdout
```

## Common Patterns

### Pattern 1: Menu Navigation
```python
test_input = "8\n"  # Exit; the main menu is printed before the prompt
stdout, _, _ = run_cli_command(test_input)
assert "--- МЕНЮ ---" in stdout
```

### Pattern 2: Chat Creation Flow (quick path)
```python
from e2e_helpers import _QUICK_CHAT

test_input = _QUICK_CHAT + "/menu\n8\n"
stdout, _, _ = run_cli_command(test_input)
assert "Используются настройки по умолчанию." in stdout
```

### Pattern 3: Command Testing
```python
test_input = _QUICK_CHAT + "/help\n/menu\n8\n"
stdout, _, _ = run_cli_command(test_input)
assert "/summary" in stdout          # help lists the command
assert "--- ДОСТУПНЫЕ КОМАНДЫ ---" in stdout
```

### Pattern 4: Error Handling
```python
test_input = "99\n8\n"  # invalid main-menu option, then exit
stdout, _, _ = run_cli_command(test_input)
assert "Неверный выбор, попробуйте снова." in stdout
```

### Pattern 5: Scenario Mock (pinning agent responses)
```python
from e2e_helpers import _QUICK_CHAT, mock_llm, run_cli_command
from ground_truth import get_messages_by_name

scenario = mock_llm(responses=[{"content": "ТОЧНЫЙ ОТВЕТ", "reasoning": "r"}])
run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n", mock=scenario)

assistants = [m for m in get_messages_by_name("Чат 1") if m["role"] == "assistant"]
assert assistants[0]["content"] == "ТОЧНЫЙ ОТВЕТ"
```

### Pattern 6: Ground Truth
```python
from ground_truth import get_agent_by_name, get_settings

run_cli_command(_QUICK_CHAT + "привет\n/menu\n8\n")
settings = get_settings(get_agent_by_name("Чат 1"))
assert settings["model_id"] == "aliceai-llm-flash/latest"
```

### Pattern 7: Multiple Operations in Single Subprocess
When testing scenarios that require several operations in one session (e.g., creating multiple chats, then viewing the list), **perform them within a single subprocess**. Persisted state (SQLite + files) does survive across subprocesses — that is exactly what ground truth relies on — but a single subprocess avoids Windows file-locking flakes (`WinError 32`) and keeps the interactive session (`current_chat`, menu position) coherent.

**Rationale:**
- Fewer process starts = faster tests
- No risk of `WinError 32` from rapid create/delete of the storage dir between subprocesses
- The interactive session state is preserved naturally

**Example:**
```python
# ✅ CORRECT: single subprocess — all operations in one session
test_input = (
    "1\n"           # New Chat
    "y\n"
    "Chat A\n"      # Name
    "\n"            # System prompt
    "1\n"           # Model
    "\n\n\n\n\n\n"  # Default settings
    "1\n"           # DefaultStrategy
    "/menu\n"       # Return to main menu (NOT exit)
    "1\n"           # New Chat again
    "y\n"
    "Chat B\n"      # Name
    "\n"
    "1\n"
    "\n\n\n\n\n\n"
    "1\n"
    "/menu\n"       # Return to main menu
    "2\n"           # View chat list
    "8\n"           # Exit
)
stdout, _, _ = run_cli_command(test_input)
assert "Chat A" in stdout and "Chat B" in stdout
```

**Key Commands for Multi-Operation Tests:**
- `/menu` - Return to main menu without exiting (preserves session state)
- option `8` - Exit application (only use at the very end)
- option `2` - View chat list (verify state)

This pattern is used by tests like `test_tc_122_concurrent_chat_operations`, which verify that multiple chats coexist in the database. State is still asserted through ground truth (e.g. `get_agent_by_name("Chat A")`).

## Troubleshooting

### Test Fails with Timeout

**Symptom:** `subprocess.TimeoutExpired`

**Causes:**
- CLI waiting for more input
- Infinite loop in application
- Deadlock

**Solution:**
1. Increase timeout if legitimate long operation
2. Verify test_input includes all required prompts
3. Check for missing exit condition

### Test Fails with Assertion Error

**Symptom:** Expected text not in stdout

**Causes:**
- Wrong input sequence
- Application behavior changed
- Encoding issues

**Solution:**
1. Print stdout for debugging: `print(stdout)`
2. Verify input matches current CLI prompts
3. Check for platform-specific line endings

### Tests Pass Locally but Fail in CI

**Causes:**
- Different working directory
- Missing environment variables
- Path resolution issues
- APPLICATION_MODE not set correctly

**Solution:**
1. Always use `Path(__file__).parent` for paths
2. Ensure `APPLICATION_MODE=TEST` is set in test environment
3. Verify cwd is set correctly in subprocess call
4. Check that the per-worker test-data directory is writable

### Scenario Mock Has No Effect

**Symptom:** `run_cli_command(..., mock=...)` still returns the default echo response.

**Causes:**
- `mock` was not actually passed (or `MOCK_LLM_SCENARIO` is invalid JSON, in which case it is ignored).
- The chat was created and the response captured before the provider was constructed with the scenario (should not happen — the env var is set for the whole subprocess).

**Solution:**
1. Pass `mock=mock_llm(...)` (or a raw JSON string) to `run_cli_command`.
2. Remember `responses` are consumed in order; add a `default` if the flow makes more calls than expected.
3. Use `json_object` for memory-extraction requests.

### Ground Truth Returns Empty / None

**Symptom:** `get_agent_by_name(...)` is `None`, `get_messages(...)` is empty.

**Causes:**
- Reading before the subprocess exits (state not flushed yet).
- Name/identifier mismatch (chat auto-named `Чат N`; profiles use UUID ids).
- Reading the wrong storage dir (not the current worker's).

**Solution:**
1. Read ground truth only after `run_cli_command` returns.
2. Assert on the exact name/identifier the flow produced.
3. Use the helpers in `ground_truth.py` (they resolve the worker dir for you).

## Quick Reference

### Running Tests
```bash
# All E2E tests (parallel by default)
poetry run pytest cli_tests/ -v

# Specific Use Case
poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings -n0 -v

# Specific test case
poetry run pytest cli_tests/test_uc001_create_chat_with_all_settings.py::TestUC001_CreateChatWithAllSettings::test_tc_001_quick_chat_creation_with_defaults -n0 -v

# Smoke test (standalone)
poetry run python cli_tests/smoke_test.py

# Scenario-mock reference tests
poetry run pytest cli_tests/test_mock_llm_scenarios.py -n0 -v
```

### Test Coverage
- **~180 pytest tests** covering the use case files under `docs/uc/`
- **25 use cases** (`uc-001` … `uc-025`) plus infrastructure tests (scenario mocks)
- **Specification traceability** via the `TestUCxxx_...` / `test_tc_xxx_...` naming convention
- **Complete data isolation** via `APPLICATION_MODE=TEST` and per-worker storage dirs

### Key Files
| File | Purpose |
|------|---------|
| `docs/cli_e2e_testing_guide.md` | This documentation |
| `cli_tests/conftest.py` | Autouse per-worker cleanup fixture + DB init |
| `cli_tests/e2e_helpers.py` | Shared helpers: `run_cli_command`, `mock_llm`, worker paths, `ollama_available` |
| `cli_tests/ground_truth.py` | Read-only accessors for persisted state (SQLite + pickles) |
| `cli_tests/test_mock_llm_scenarios.py` | Reference tests for scenario mocks |
| `cli_tests/smoke_test.py` | Standalone smoke test (wraps a few critical cases) |
| `cli_tests/test_ucXXX_*.py` | Full E2E suite, one file per test class |
| `mock_llm.py` | Scenario parser (`MockScenario`, `load_scenario_from_env`) |
| `pyproject.toml` | `[tool.pytest.ini_options]`: `addopts = "-n auto"`, `testpaths` |
| `docs/cli_spec.md` | CLI specification + use case index |
| `docs/uc/` | One use case per file with alternative flows and related test cases |

### Core Principles Summary
1. ❌ No business-state fixtures (only the autouse cleanup fixture)
2. ✅ Subprocess-only interaction with the CLI
3. ✅ Dynamic path resolution
4. ✅ Specification traceability
5. ✅ Timeout enforcement
6. ✅ `APPLICATION_MODE=TEST` + per-worker `AI_CHAT_TEST_DATA_DIR` for isolation
7. ✅ Complete output capture (exit code + `stderr` enforced by `run_cli_command`)
8. ✅ Clean per-worker storage dir before each test
9. ✅ **Single subprocess for multi-operation tests**
10. ✅ **Assert ground truth (DB + files)**, not just output substrings
11. ✅ **Per-test behaviour via `MOCK_LLM_SCENARIO`** instead of hardcoded mock output
12. ✅ Parallel by default (`pytest-xdist -n auto`); `-n0` only for debugging

## Common Issues and Solutions

| Issue                                      | Solution                                                              |
| ------------------------------------------ | --------------------------------------------------------------------- |
| `[WinError 267] Invalid directory`         | Use `Path(__file__).parent` instead of hardcoded paths                |
| Test hangs indefinitely                    | Add `timeout` parameter to `communicate()`                            |
| `UnicodeEncodeError` (Windows console)     | Use ASCII markers (`[PASS]`/`[FAIL]`) and/or `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` |
| Different behavior on Windows/Linux        | Test on both platforms; use cross-platform path handling              |
| `sqlite3.OperationalError: no such table`  | Ensure `DatabaseConnection.init_tables(Base.metadata)` runs after `APPLICATION_MODE=TEST` is set |
| Tests use production data                  | Verify `APPLICATION_MODE=TEST` is set before running CLI              |
| Default echo mock not suitable             | Pass a scenario: `run_cli_command(..., mock=mock_llm(responses=[...]))` |
| Ground-truth helper returns `[]`/`None`    | Read state only after the subprocess exits; confirm paths use the worker dir |
| Database path conflicts                    | Confirm per-worker `test-data-<worker>` and `./data` are separate     |
| `test-data*` dirs left after a run         | Expected on failure (kept for debugging); removed on success; also `gitignore`d |
| `[WinError 32] Process cannot access file` (Windows) | **SQLite file locking issue on Windows**. See dedicated section below. |
| State appears "lost" between operations    | Keep multi-step flows in one subprocess (see [Pattern 7](#pattern-7-multiple-operations-in-single-subprocess)) |

## Windows-Specific: SQLite File Locking Issue

### Problem

On Windows, you may encounter errors like:
```
PermissionError: [WinError 32] Процесс не может получить доступ к файлу,
так как этот файл занят другим процессом: 'D:\\projects\\ai_challenge\\test-data\\agents.db'
```

This occurs because SQLite on Windows aggressively locks database files, and the lock may not be released immediately after the CLI process exits, especially when tests run in rapid succession.

### Root Cause

- Windows file locking is stricter than on Unix/Linux
- SQLite connections may not close instantly
- pytest runs tests quickly, sometimes before the OS releases the file lock
- The autouse cleanup fixture may try to delete the storage dir while a handle is still open

### Solution

The `setup_clean_test_environment` fixture (in `cli_tests/conftest.py`) closes its own
`DatabaseConnection` before yielding, which releases the file handle for the subprocess.
Each xdist worker also uses a private `test-data-<worker>/` directory, which reduces
contention. If errors persist, remove all worker dirs and re-run:

```powershell
# PowerShell
Get-ChildItem -Directory -Filter 'test-data*' | Remove-Item -Recurse -Force

# Then run tests
poetry run pytest cli_tests/ -v
```

### Prevention

Keep the fixture's `db.close()` before `yield`, and do not open long-lived SQLite
connections (or hold files open) in tests themselves — read ground truth after the
subprocess has exited.

