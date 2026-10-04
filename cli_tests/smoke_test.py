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
    print("  - TC-014: Send Multiple Messages (mock provider + history)")
    print("  - TC-032: Settings Change With Confirmation (storage R/W)")
    print("  - TC-029: Create Branch And Switch (branching + storage)")
    print("-" * 50)

    project_root = get_project_root()

    try:
        # Run pytest on multiple test cases that cover different aspects:
        # - TC-014: Tests mock provider interaction and message history
        # - TC-032: Tests settings storage read/write operations
        # - TC-029: Tests branching and storage operations
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "cli_tests/test_uc004_send_message_and_receive_response.py::TestUC004_SendMessageAndReceiveResponse::test_tc_014_send_multiple_messages",
                "cli_tests/test_uc005_view_and_change_settings_in_chat.py::TestUC005_ViewAndChangeSettingsInChat::test_tc_032_settings_change_with_confirmation",
                "cli_tests/test_uc011_create_chat_branch.py::TestUC011_CreateChatBranch::test_tc_029_create_branch_and_switch",
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
