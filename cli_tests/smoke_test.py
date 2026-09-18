#!/usr/bin/env python3
"""
Smoke test for CLI chat application.
Tests basic interaction with the mock provider in test mode.

This is a lightweight wrapper around the e2e test infrastructure,
running a minimal test scenario to verify the application works.
"""

import os

# ВАЖНО: Установить APPLICATION_MODE ДО импорта любых модулей проекта,
# так как config.py читает эту переменную при загрузке модуля
os.environ["APPLICATION_MODE"] = "TEST"

import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Dynamically resolve project root directory."""
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent


def run_smoke_test():
    """Run comprehensive smoke test scenario using pytest on multiple e2e test cases.

    This smoke test verifies:
    1. Chat creation with settings (storage interaction)
    2. Multiple message exchange (mock provider interaction)
    3. Settings modification (storage read/write)
    4. Branching functionality (storage operations)
    5. Menu navigation
    """

    print("Running smoke test in TEST MODE (APPLICATION_MODE=TEST)...")
    print("-" * 50)
    print("Testing scenarios:")
    print("  - TC-009: Send Multiple Messages (mock provider + history)")
    print("  - TC-027: Settings Change With Confirmation (storage R/W)")
    print("  - TC-024: Create Branch And Switch (branching + storage)")
    print("-" * 50)

    project_root = get_project_root()

    try:
        # Run pytest on multiple test cases that cover different aspects:
        # - TC-009: Tests mock provider interaction and message history
        # - TC-027: Tests settings storage read/write operations
        # - TC-024: Tests branching and storage operations
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "cli_tests/test_cli_e2e.py::TestUC004_SendMessageAndReceiveResponse::test_tc_009_send_multiple_messages",
                "cli_tests/test_cli_e2e.py::TestUC005_ViewAndChangeSettingsInChat::test_tc_027_settings_change_with_confirmation",
                "cli_tests/test_cli_e2e.py::TestUC011_CreateChatBranch::test_tc_024_create_branch_and_switch",
                "-v",
                "--tb=short",
            ],
            cwd=str(project_root),
            capture_output=False,
            text=True,
        )

        print("-" * 50)
        if result.returncode == 0:
            print("✅ Smoke test PASSED - All critical paths verified")
            return True
        else:
            print("❌ Smoke test FAILED")
            return False

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
