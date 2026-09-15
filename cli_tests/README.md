# CLI Testing Guide

## Overview

This guide documents the experience and best practices for testing CLI applications in this project, particularly focusing on cross-platform compatibility between Linux (CI/development environment) and Windows (local development).

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

### 7. Use Explicit Test Mode Flag

The application now supports an explicit `--test` flag for running in test mode with the Mock provider:

```python
# Always use --test flag in automated tests
process = subprocess.Popen(
    [sys.executable, "main_cli.py", "--test"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd=str(project_root),
)
```

This ensures:

- Tests always run with the Mock provider regardless of environment variables
- Production mode explicitly requires API credentials
- Clear separation between test and production scenarios

## Running Tests

### Automated Tests Must Use Test Mode

**IMPORTANT:** All automated test scripts **MUST** be executed in the application's **TEST MODE** (`--test` flag).

This ensures:

- Tests run without requiring real API keys or environment variables
- Tests use the `MockLlmProvider` for predictable, fast, and isolated execution
- No accidental costs or external dependencies during testing

### From Any Location

```bash
# Navigate to the test directory
cd cli_tests

# Run the smoke test (uses --test flag by default)
python smoke_test.py
```

### With Verbose Output

```bash
python -u smoke_test.py
```

### Manual Testing Modes

You can run the application manually in two modes:

**1. Test Mode (Recommended for Development/Testing)**
Uses the Mock LLM provider. No API keys required.

```bash
python ../main_cli.py --test
```

**2. Production Mode (Default)**
Uses the real Yandex Cloud LLM provider. Requires environment variables.

```bash
# Set required variables first
$env:YANDEX_CLOUD_API_KEY="your_key"
$env:YANDEX_CLOUD_FOLDER_ID="your_folder"

python ../main_cli.py
```

If variables are missing in Production Mode, the app will exit with an error.

## Common Issues and Solutions

| Issue                               | Solution                                                 |
| ----------------------------------- | -------------------------------------------------------- |
| `[WinError 267] Invalid directory`  | Use `Path(__file__).parent` instead of hardcoded paths   |
| Test hangs indefinitely             | Add `timeout` parameter to `communicate()`               |
| Encoding errors                     | Use `text=True` and ensure consistent encoding           |
| Different behavior on Windows/Linux | Test on both platforms; use cross-platform path handling |
| `EnvironmentError` in test mode     | Ensure `--test` flag is passed to the application        |
| Mock provider not used              | Verify `--test` flag is present; check app_mode module   |
