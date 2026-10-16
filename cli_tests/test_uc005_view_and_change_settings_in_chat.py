"""E2E tests: TestUC005_ViewAndChangeSettingsInChat."""

from e2e_helpers import run_cli_command
from ground_truth import get_agent_by_name, get_settings


class TestUC005_ViewAndChangeSettingsInChat:
    """
    Use Case UC-005: View and Change Settings In-Chat

    Test Cases:
    - TC-016: View Settings
    - TC-017: Change Settings With Empty Inputs Disables Parameters
    - TC-032: Settings Change With Confirmation
    - TC-033: Settings Change Cancelled
    """

    def test_tc_016_view_settings(self):
        """
        TC-016: View Settings

        Steps:
        1. Enter chat with configured settings
        2. Type "/settings"
        3. Verify current settings displayed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ViewSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "n\n"  # Don't change
            "4\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ТЕКУЩИЕ НАСТРОЙКИ ---" in stdout
        assert "Температура:" in stdout
        settings = get_settings(get_agent_by_name("ViewSettings"))
        assert settings["model_id"] == "gpt-oss-120b/latest"
        assert settings["provider"] == "yandex"
        assert "temperature" not in settings

    def test_tc_017_change_settings_with_empty_inputs_disables_parameters(self):
        """
        TC-017: Change Settings With Empty Inputs Disables Parameters

        Steps:
        1. Type "/settings"
        2. Change only temperature
        3. Press Enter for others
        4. Verify only temperature changed
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "PartialSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Change settings
            "1\n"  # Модель 1
            "0.8\n"  # Новая температура
            "\n"  # Top P (пусто -> отключён)
            "\n"  # Top K (пусто -> 0/отключено)
            "\n"  # Max Tokens (пусто -> без ограничений)
            "\n"  # Reasoning effort (пусто -> default 1)
            "\n"  # Context window (пусто -> 200k)
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[OK] Настройки обновлены!" in stdout
        settings = get_settings(get_agent_by_name("PartialSettings"))
        assert settings["temperature"] == 0.8
        assert settings["model_id"] == "gpt-oss-120b/latest"
        assert "top_p" not in settings
        assert "max_tokens" not in settings

    def test_tc_032_settings_change_with_confirmation(self):
        """
        TC-032: Settings Change With Confirmation

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "y"
        4. Verify all settings prompts shown
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "ConfirmSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "y\n"  # Подтверждение изменения
            "1\n"  # Модель 1
            "0.8\n"  # Новая температура
            "\n"  # Top P (пусто -> отключён)
            "\n"  # Top K (пусто -> отключено)
            "\n"  # Max Tokens (пусто -> без ограничений)
            "\n"  # Reasoning effort (default)
            "\n"  # Context window (default)
            "/menu\n"  # Выход в меню
            "8\n"  # Exit
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Изменить настройки?" in stdout
        settings = get_settings(get_agent_by_name("ConfirmSettings"))
        assert settings["temperature"] == 0.8
        assert settings["model_id"] == "gpt-oss-120b/latest"

    def test_tc_033_settings_change_cancelled(self):
        """
        TC-033: Settings Change Cancelled

        Steps:
        1. Type "/settings"
        2. Verify prompt "Изменить настройки? (y/n):"
        3. Enter "n"
        4. Verify return to chat without changes
        """
        test_input = (
            "1\n"  # Новый чат
            "y\n"  # Хотите настроить? (y/n)
            "CancelSettings\n"  # Название
            "\n"  # Skip system prompt
            "1\n"  # Model 1
            "\n" + "\n" + "\n" + "\n" + "\n" + "\n"  # Settings (6 times)
            "1\n"  # DefaultStrategy
            "/settings\n"  # View settings
            "n\n"  # Cancel change
            "4\n"  # Exit
        )

        run_cli_command(test_input)

        settings = get_settings(get_agent_by_name("CancelSettings"))
        assert "temperature" not in settings
        assert settings["model_id"] == "gpt-oss-120b/latest"
