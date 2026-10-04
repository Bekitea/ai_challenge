"""E2E tests: TestUC012_ViewGlobalMemoryFromMenu."""

from e2e_helpers import run_cli_command


class TestUC012_ViewGlobalMemoryFromMenu:
    """
    Use Case UC-012: View Global Memory from Menu

    Test Cases:
    - TC-046: View Global Memory From Main Menu
    - TC-047: View Global Memory Empty State
    - TC-048: View Global Memory With Facts
    """

    def test_tc_046_view_global_memory_from_main_menu(self):
        """
        TC-046: View Global Memory From Main Menu

        Steps:
        1. Start application, stay in Main Menu (no active chat)
        2. Select option 4 (Global Memory) from menu
        3. Verify header displayed: "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---"
        4. Verify return to menu
        """
        # Main Menu has option 4 for Global Memory, accessible without active chat
        test_input = (
            "4\n"  # Select Global Memory
            "6\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        # Should display global memory header
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout
        # Should return to menu or exit cleanly

    def test_tc_047_view_global_memory_empty_state(self):
        """
        TC-047: View Global Memory Empty State

        Steps:
        1. Start application (fresh DB with no global memory saved yet)
        2. Select option 4 to view global memory
        3. Verify header is displayed
        4. Verify message about empty memory is displayed
        5. Verify returns to menu
        """
        test_input = (
            "4\n"  # View global memory (should be empty on fresh start)
            "6\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "ГЛОБАЛЬНАЯ ПАМЯТЬ" in stdout
        # Empty memory shows "(память пуста)" message
        assert "память пуста" in stdout.lower()

    def test_tc_048_view_global_memory_with_facts(self):
        """
        TC-048: View Global Memory With Facts

        Steps:
        1. Create a new chat
        2. Send a message (mock provider extracts facts into global memory)
        3. Answer 'n' to reasoning prompt
        4. Use /menu to return to main menu
        5. Select option 3 to view global memory
        6. Verify header is displayed
        7. Verify facts are displayed as numbered list
        8. Verify separator line
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "FactsMemoryTest\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n\n\n\n\n"  # Settings (5 times)
            "1\n"  # DefaultStrategy
            "Расскажи о себе\n"  # Send message to trigger memory extraction
            "n\n"  # Don't show reasoning
            "/menu\n"  # Return to main menu
            "4\n"  # View global memory (should have facts from mock)
            "6\n"  # Exit
        )

        stdout, stderr, returncode = run_cli_command(test_input)

        assert returncode == 0, f"App failed with stderr: {stderr}"

        # Check header
        assert "--- ГЛОБАЛЬНАЯ ПАМЯТЬ ---" in stdout, "Header should be displayed"

        # Check separator (40 dashes)
        assert "-" * 40 in stdout, "Separator line should be displayed"

        # Mock provider returns exactly these two facts when JSON format is requested
        expected_fact_1 = (
            "1. Пользователь предпочитает использовать Python для разработки"
        )
        expected_fact_2 = "2. Пользователь работает в Москве"

        # Verify both facts are present in the output
        assert expected_fact_1 in stdout, (
            f"First fact should be displayed: {expected_fact_1}"
        )
        assert expected_fact_2 in stdout, (
            f"Second fact should be displayed: {expected_fact_2}"
        )
