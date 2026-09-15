#!/usr/bin/env python3
"""
Smoke test for CLI chat application.
Tests basic interaction with the mock provider.
"""

import subprocess
import sys
from pathlib import Path


def run_smoke_test():
    """Run basic smoke test scenario."""

    # Test input: select option 1 (chat), send message, then exit
    test_input = "1\nHello, how are you?\n0\n"

    print("Running smoke test...")
    print(f"Test input:\n{test_input}")
    print("-" * 50)

    try:
        # Determine project root directory dynamically
        # This works both in CI (/workspace) and locally
        script_dir = Path(__file__).parent.absolute()
        project_root = script_dir.parent

        # Run the CLI application with test input
        process = subprocess.Popen(
            [sys.executable, "main_cli.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(project_root),
        )

        stdout, stderr = process.communicate(input=test_input, timeout=30)

        print("STDOUT:")
        print(stdout)
        print("-" * 50)

        if stderr:
            print("STDERR:")
            print(stderr)
            print("-" * 50)

        # Check if the output contains expected elements
        success = True

        # Check for menu display (checking for multiple possible menu items)
        if (
            "1. Новый чат" not in stdout
            and "1. Start chat" not in stdout
            and "МЕНЮ" not in stdout
        ):
            print("❌ Menu not displayed correctly")
            success = False
        else:
            print("✓ Menu displayed correctly")

        # Check for model selection
        if "Выберите модель" not in stdout and "Select model" not in stdout:
            print("⚠ Model selection not found (may be OK depending on flow)")
        else:
            print("✓ Model selection displayed")

        # Check for mock provider warning if no env vars
        if "YANDEX_CLOUD_API_KEY" in stderr or "MockLlmProvider" in stdout:
            print("✓ Mock provider is being used (expected when no API keys)")

        # Check if application processed input
        if "Hello, how are you?" in stdout or process.returncode == 0:
            print("✓ Application processed input successfully")
        else:
            print("⚠ Application may not have processed input correctly")

        # Check exit code
        if process.returncode == 0:
            print("✓ Application exited with code 0")
        else:
            print(f"❌ Application exited with code {process.returncode}")
            success = False

        print("-" * 50)
        if success:
            print("✅ Smoke test PASSED")
            return True
        else:
            print("❌ Smoke test FAILED")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Test timed out")
        process.kill()
        return False
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
