# CLI Testing Guide

## Overview

This guide documents the experience and best practices for testing CLI applications in this project, particularly focusing on cross-platform compatibility between Linux (CI/development environment) and Windows (local development).

## Test Isolation and Data Management

### Test Mode and Data Isolation

**CRITICAL:** All automated tests MUST run in **TEST MODE** to ensure complete isolation from production data.

**Mechanism:** The application uses the `APPLICATION_MODE` environment variable to determine data storage locations:

| Mode | Environment Variable | Database Path | Chat History Path |
|------|---------------------|---------------|-------------------|
| **PROD** (default) | `APPLICATION_MODE=PROD` or not set | `./data/app.db` | `./data/chat_history/` |
| **TEST** | `APPLICATION_MODE=TEST` | `./test-data/app.db` | `./test-data/chat_history/` |

**How It Works:**

1. **Before each test:** Test framework sets `APPLICATION_MODE=TEST` in the subprocess environment
2. **CLI startup:** Application reads `APPLICATION_MODE` and configures paths accordingly
3. **Test execution:** All data operations use isolated `./test-data/` directory
4. **After each test:** `./test-data/` directory is completely removed

**Benefits:**

- ✅ Production data in `./data/` is never touched by tests
- ✅ Each test starts with a clean slate (no residual state)
- ✅ Tests can run in parallel without conflicts
- ✅ Failed tests leave artifacts for debugging (until next test run)

### Test Setup and Teardown Pattern

All E2E tests inherit from `BaseCLITest`, which provides automatic isolation:

```python
class BaseCLITest:
    """Base class providing test isolation."""

    def setUp(self):
        """Called before each test."""
        # 1. Remove old test-data directory
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)

        # 2. Create fresh test-data directory
        os.makedirs(TEST_DATA_DIR, exist_ok=True)

        # 3. Initialize database tables
        init_db()

    def tearDown(self):
        """Called after each test."""
        # Optional: Clean up test-data immediately
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
```

**Example Test:**

```python
class TestUC001_CreateChatWithAllSettings(BaseCLITest):

    def test_tc_001_create_chat_default_values(self):
        # setUp() already ran - test-data is clean and DB initialized

        test_input = "1\n\n\n1\n\n\n\n\n\n1\n4\n"
        env = os.environ.copy()
        env["APPLICATION_MODE"] = "TEST"  # Critical!

        stdout, stderr, returncode = run_cli_command(test_input, env=env)

        assert returncode == 0
        assert "Чат создан" in stdout

        # tearDown() will run after - cleans up test-data
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

### Basic Smoke Test Template

```python
#!/usr/bin/env python3
"""
Smoke test for CLI application.
"""

import subprocess
import sys
from pathlib import Path

def run_smoke_test():
    # Define test input scenario
    test_input = "1\nTest message\n0\n"

    # Resolve paths dynamically
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent

    try:
        # Run the application
        process = subprocess.Popen(
            [sys.executable, "main_cli.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
        )

        # Send input and get output
        stdout, stderr = process.communicate(input=test_input, timeout=30)

        # Validate results
        assert "Expected menu text" in stdout
        assert process.returncode == 0

        print("✅ Test PASSED")
        return True

    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        process.kill()
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
```

## Best Practices

### 1. Always Use Dynamic Paths

Never hardcode absolute paths. Always resolve them relative to the test script location.

### 2. Set Reasonable Timeouts

Always specify a `timeout` parameter in `communicate()` to prevent hanging tests.

### 3. Capture Both stdout and stderr

Some applications write warnings or errors to stderr. Capture both streams for complete debugging information.

### 4. Use Descriptive Test Names

Name test files descriptively: `smoke_test.py`, `test_chat_flow.py`, etc.

### 5. Document Test Scenarios

Include comments explaining what each test scenario validates.

### 6. Handle Mock Providers Gracefully

When API keys are not available, ensure your application falls back to mock providers and tests verify this behavior.

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
- Tests use isolated `./test-data/` directory (production data safe)
- Each test starts with a clean database state
- Clear separation between test and production scenarios

## Running Tests

### Automated Tests Must Use Test Mode

**IMPORTANT:** All automated test scripts **MUST** set `APPLICATION_MODE=TEST` environment variable.

This ensures:

- Tests run without requiring real API keys
- Tests use the `MockLlmProvider` for predictable, fast, and isolated execution
- Tests use isolated `./test-data/` directory (production data in `./data/` is never touched)
- No accidental costs or external dependencies during testing
- Each test starts with a clean database state

### From Any Location

```bash
# Navigate to the test directory
cd cli_tests

# Run the smoke test (sets APPLICATION_MODE=TEST internally)
python smoke_test.py
```

### Running E2E Tests with pytest

The project includes pytest-based E2E tests that emulate real user interaction via subprocess calls. These tests:

- Use `subprocess.Popen` to spawn actual CLI processes (no mocking at Python level)
- Send input via stdin (simulating keyboard input)
- Capture stdout/stderr (simulating terminal output)
- Set `APPLICATION_MODE=TEST` for complete isolation
- Do NOT use pytest fixtures - each test is self-contained to maximize realism
- Directly map to test cases from `cli_spec.md` specification

```bash
# Run all E2E tests (APPLICATION_MODE=TEST is set automatically in tests)
pytest cli_tests/test_cli_e2e.py -v

# Run specific test class (Use Case)
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings -v

# Run specific test
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings::test_tc_001_create_chat_default_values -v
```

**Note for Windows Users:** If you encounter `[WinError 32] Process cannot access file` errors, see the "Windows-Specific: SQLite File Locking Issue" section below for solutions.

### Test Organization and Naming Convention

**IMPORTANT:** All E2E tests follow a strict naming convention for direct traceability to the specification:

- **Test classes** are named after Use Cases: `TestUC001_CreateChatWithAllSettings`
- **Test methods** are named after Test Cases: `test_tc_001_create_chat_default_values`
- Format: `test_tc_XXX_<description>` where `XXX` is the test case number from `cli_spec.md`

This ensures:
1. Easy mapping between specification and implementation
2. Clear coverage tracking
3. Simple identification of missing tests

### Why This Approach?

The existing smoke test (`smoke_test.py`) and new pytest E2E tests intentionally avoid pytest fixtures and direct function calls because:

1. **Real User Simulation**: Tests interact with the CLI exactly as a real user would - through stdin/stdout
2. **Cross-Platform Compatibility**: Subprocess approach works identically on Windows, Linux, and macOS
3. **No Hidden State**: Each test is completely independent, avoiding fixture-related side effects
4. **True Integration Testing**: Tests verify the entire stack - from CLI parsing to database operations
5. **Specification Traceability**: Direct mapping to `cli_spec.md` ensures complete coverage

```python
# Example test structure (from test_cli_e2e.py)
class TestUC001_CreateChatWithAllSettings:
    \"\"\"Use Case UC-001: Create New Chat with All Settings\"\"\"

    def test_tc_001_create_chat_default_values(self):
        \"\"\"
        TC-001: Create Chat with Default Values

        Steps:
        1. Select "New Chat"
        2. Press Enter (default name)
        3. Press Enter (skip prompt)
        4. Select model 1
        5. Press Enter (disable temp)
        6. Verify chat created
        \"\"\"
        test_input = (
            "1\\n"           # Новый чат
            "\\n"            # Default name
            "\\n"            # Skip system prompt
            "1\\n"           # Model 1
            "\\n"            # Temperature disabled
            "4\\n"           # Exit
        )
        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0
        assert "Чат создан" in stdout
```

### Running Tests in Different Modes

**Test Mode (Default for Automated Tests):**
```bash
# APPLICATION_MODE=TEST is set automatically in tests
pytest cli_tests/test_cli_e2e.py -v
```

**Smoke Test (comprehensive scenario):**
```bash
# Runs multiple test cases via pytest to verify critical paths:
# - TC-009: Multiple message exchange (mock provider + history)
# - TC-027: Settings modification (storage read/write)
# - TC-024: Branching operations (storage + navigation)
python cli_tests/smoke_test.py
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

### 1. No Fixtures Policy

**Rule:** E2E tests MUST NOT use pytest fixtures for test setup/teardown.

**Rationale:**
- Each test must be completely self-contained
- Avoids hidden state between tests
- Ensures tests can run in any order
- Maximizes realism (real user has no "fixtures")

**Example:**
```python
# ❌ WRONG: Using fixtures
@pytest.fixture
def create_test_chat():
    # Creates chat in database
    yield chat
    # Cleanup

def test_something(create_test_chat):
    ...

# ✅ CORRECT: Self-contained test
def test_tc_001_create_chat_default_values(self):
    """Test creates its own state via CLI interaction."""
    test_input = "1\n\n\n1\n\n4\n"
    stdout, stderr, returncode = run_cli_command(test_input)
    assert "Чат создан" in stdout
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
stdout, stderr, returncode = run_cli_command(test_input)
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

**Rule:** Test names MUST directly map to test cases in `cli_spec.md`.

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
        """Directly maps to TC-001 in cli_spec.md."""
        ...

    def test_tc_002_create_chat_custom_settings(self):
        """Directly maps to TC-002 in cli_spec.md."""
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
- Isolated data storage (`./test-data/` vs `./data/`)
- Clean state for each test

**Example:**
```python
# ❌ WRONG: Production mode (uses ./data/)
env = os.environ.copy()
process = subprocess.Popen([sys.executable, "main_cli.py"], ..., env=env)

# ✅ CORRECT: Test mode (uses ./test-data/)
env = os.environ.copy()
env["APPLICATION_MODE"] = "TEST"
process = subprocess.Popen([sys.executable, "main_cli.py"], ..., env=env)
```

### 7. Complete Output Capture

**Rule:** ALWAYS capture both `stdout` AND `stderr`.

**Rationale:**
- Complete debugging information
- Catch warnings and errors
- Verify correct output streams

**Example:**
```python
# ❌ WRONG: Only stdout
stdout = process.stdout.read()

# ✅ CORRECT: Both streams
stdout, stderr = process.communicate(input=test_input, timeout=30)
```

## Test Case Design Guidelines

### Structuring Test Input

Build input strings that mirror real user keystrokes:

```python
test_input = (
    "1\n"           # Menu option: New Chat
    "My Chat\n"     # Chat name
    "You are helpful\n"  # System prompt
    "1\n"           # Model selection
    "0.7\n"         # Temperature
    "\n"            # Skip (default)
    "4\n"           # Exit
)
```

### Assertion Strategy

Focus on observable behavior:

```python
# ✅ Check return code
assert returncode == 0

# ✅ Check success messages
assert "Чат создан" in stdout

# ✅ Check menu options
assert "1. Новый чат" in stdout

# ✅ Check error handling
assert "Ошибка" in stdout or "Error" in stdout

# ❌ Avoid: Internal state checks (use CLI commands instead)
```

### Handling Sequential Dependencies

When tests need prior state, create it within the test:

```python
def test_tc_008_return_to_chat_with_active_chat(self):
    """TC-008: Must have active chat first."""
    # Step 1: Create chat
    # Step 2: Send message (makes it active)
    # Step 3: Go to menu
    # Step 4: Use "Return to chat"
    test_input = (
        "1\n"           # New chat
        "Test\n"        # Name
        "\n"            # Skip prompt
        "1\n"           # Model
        "\n\n\n\n\n"    # Defaults
        "Hello\n"       # Send message
        "/menu\n"       # Go to menu
        "3\n"           # Return to chat
        "4\n"           # Exit
    )
    stdout, stderr, returncode = run_cli_command(test_input)
    assert "Активный чат" in stdout
```

## Common Patterns

### Pattern 1: Menu Navigation
```python
test_input = "4\n"  # Exit to menu
assert "МЕНЮ" in stdout
```

### Pattern 2: Chat Creation Flow
```python
test_input = (
    "1\n"      # New Chat
    "Name\n"   # Chat name
    "1\n"      # Model
    "\n" * 5   # Default settings
)
assert "Чат создан" in stdout
```

### Pattern 3: Command Testing
```python
test_input = (
    "1\n...\n"  # Create chat
    "/help\n"   # Help command
    "4\n"       # Exit
)
assert "/help" in stdout or "Справка" in stdout
```

### Pattern 4: Error Handling
```python
test_input = (
    "99\n"      # Invalid option
    "4\n"       # Exit
)
assert "Ошибка" in stdout or "Неверный ввод" in stdout
```

### Pattern 5: Multiple Operations in Single Subprocess
When testing scenarios that require state persistence across multiple operations (e.g., creating multiple chats, then viewing the list), **all operations MUST be performed within a single subprocess** to avoid SQLite connection and file locking issues.

**Rationale:**
- Each subprocess creates a new SQLite connection
- Database state may not persist between subprocess invocations due to connection isolation
- Windows file locking can cause `WinError 32` when rapid subprocess creation/deletion occurs
- Ensures atomic test execution without intermediate cleanup

**Example:**
```python
# ❌ WRONG: Multiple subprocesses - state not preserved
run_cli_command("1\nChat A\n...\n4\n")  # Create Chat A, exit
run_cli_command("1\nChat B\n...\n4\n")  # Create Chat B, exit
stdout, _, _ = run_cli_command("2\n4\n")  # List chats - FAILS: no chats found

# ✅ CORRECT: Single subprocess - all operations atomic
test_input = (
    "1\n"           # New Chat
    "Chat A\n"      # Name
    "...\n"         # Settings
    "/menu\n"       # Return to menu (NOT exit)
    "1\n"           # New Chat again
    "Chat B\n"      # Name
    "...\n"         # Settings
    "/menu\n"       # Return to menu
    "2\n"           # View chat list
    "4\n"           # Exit
)
stdout, stderr, returncode = run_cli_command(test_input)
assert "Chat A" in stdout or "Chat B" in stdout
```

**Key Commands for Multi-Operation Tests:**
- `/menu` - Return to main menu without exiting (preserves session state)
- `/exit` or option `4` - Exit application (only use at the very end)
- Option `2` - View chat list (verify state)

This pattern is critical for tests like `test_tc_020_concurrent_chat_operations` which verify that multiple chats can coexist in the database.

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
4. Check that test-data directory is writable

## Quick Reference

### Running Tests
```bash
# All E2E tests
pytest cli_tests/test_cli_e2e.py -v

# Specific Use Case
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings -v

# Specific test case
pytest cli_tests/test_cli_e2e.py::TestUC001_CreateChatWithAllSettings::test_tc_001_create_chat_default_values -v

# Smoke test (standalone)
python cli_tests/smoke_test.py
```

### Test Coverage
- **40 test cases** covering all requirements from `cli_spec.md`
- **11 Use Cases** organized by user workflow
- **100% specification traceability** via naming convention
- **Complete data isolation** via APPLICATION_MODE and test-data directory

### Key Files
| File | Purpose |
|------|---------|
| `cli_tests/README.md` | This documentation |
| `cli_tests/smoke_test.py` | Basic smoke test (standalone script) |
| `cli_tests/test_cli_e2e.py` | Full E2E test suite (pytest) |
| `cli_spec.md` | Specification with Use Cases and Test Cases |

### Core Principles Summary
1. ❌ No fixtures
2. ✅ Subprocess-only interaction
3. ✅ Dynamic path resolution
4. ✅ Specification traceability
5. ✅ Timeout enforcement
6. ✅ APPLICATION_MODE=TEST for isolation
7. ✅ Complete output capture
8. ✅ Clean test-data directory per test
9. ✅ **Single subprocess for multi-operation tests** (state persistence)

## Common Issues and Solutions

| Issue                                      | Solution                                                              |
| ------------------------------------------ | --------------------------------------------------------------------- |
| `[WinError 267] Invalid directory`         | Use `Path(__file__).parent` instead of hardcoded paths                |
| Test hangs indefinitely                    | Add `timeout` parameter to `communicate()`                            |
| Encoding errors                            | Use `text=True` and ensure consistent encoding                        |
| Different behavior on Windows/Linux        | Test on both platforms; use cross-platform path handling              |
| `sqlite3.OperationalError: no such table`  | Ensure `init_db()` is called after setting `APPLICATION_MODE=TEST`    |
| Tests use production data                  | Verify `APPLICATION_MODE=TEST` is set before running CLI              |
| Mock provider not used                     | Check `APPLICATION_MODE=TEST` is set; verify app_mode module          |
| Database path conflicts                    | Confirm test-data and data directories are separate                   |
| `[WinError 32] Process cannot access file` (Windows) | **SQLite file locking issue on Windows**. See dedicated section below. |
| State not preserved between operations     | **Use single subprocess with `/menu` command** instead of multiple subprocesses with exit |

## Windows-Specific: SQLite File Locking Issue

### Problem

On Windows, you may encounter errors like:
```
PermissionError: [WinError 32] Процесс не может получить доступ к файлу,
так как этот файл занят другим процессом: 'D:\\projects\\ai_challenge\\test-data\\agents.db'
```

This occurs because SQLite on Windows aggressively locks database files, and the lock may not be released immediately after the CLI process exits, especially when tests run in rapid succession.

### Root Cause

- Windows file locking is more strict than Unix/Linux
- SQLite connections may not close instantly
- pytest runs tests quickly, sometimes before the OS releases the file lock
- The `tearDown()` cleanup may attempt to delete `test-data/` while a handle is still open

### Solution

**Manual cleanup between runs**

If errors persist, manually remove the test-data directory before running tests:
```powershell
# PowerShell
Remove-Item -Recurse -Force test-data

# Then run tests
python -m pytest cli_tests/test_cli_e2e.py -v
```

### Prevention

The test framework includes proper cleanup in `tearDown()`.
