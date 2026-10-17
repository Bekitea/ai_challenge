"""E2E tests: TestUC001_TC063_120_CreationExtras."""

from e2e_helpers import _manual_chat, run_cli_command
from ground_truth import (
    get_agent_by_name,
    get_agent_profile_id,
    get_last_agent,
    get_settings,
    get_strategy,
)


class TestUC001_TC063_120_CreationExtras:
    """TC-063: profile-less creation; TC-120: quick-path default name counter."""

    def test_tc_063_task_profile_selection_no_profiles_available(self):
        """
        TC-063: Task Profile Selection - No Profiles Available (UC-001 §4.4.10)

        Precondition: no task profiles exist. Manual creation reaching the
        profile step must print '(нет доступных профилей)' and continue
        without attachment.
        """
        test_input = (
            _manual_chat("NoProfilesChat")
            + "/info\n"  # Профиль не привязан
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- ПРИВЯЗКА ПРОФИЛЯ ЗАДАЧИ ---" in stdout
        assert "(нет доступных профилей)" in stdout
        assert get_agent_by_name("NoProfilesChat") is not None
        assert get_agent_profile_id("NoProfilesChat") is None

    def test_tc_120_quick_creation_default_name_counter(self):
        """
        TC-120: Quick Creation Default Name Counter (UC-001 A1, A3)

        Steps:
        1. Ensure exactly 2 chats exist (two quick chats).
        2. Option 1, Enter at configure prompt -> defaults announced.
        3. Completion message names the chat 'Чат 3' (N = existing + 1).
        4. Defaults applied (model, disabled params, DefaultStrategy, no profile).
        """
        test_input = (
            "1\n\n3\n\n/menu\n"  # Чат 1 (модель + reasoning effort по умолчанию)
            + "1\n\n3\n\n/menu\n"  # Чат 2
            + "1\n"  # Третий чат
            + "\n"  # Enter на 'Хотите настроить?' -> быстрый путь
            + "3\n"  # Модель: Alice AI LLM Flash
            + "\n"  # Reasoning effort: default "none"
            + "/settings\n"
            + "n\n"
            + "/info\n"
            + "/menu\n"
            + "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Используются настройки по умолчанию." in stdout
        agent = get_last_agent()
        assert agent["name"] == "Чат 3"
        settings = get_settings(agent)
        assert settings["model_id"] == "aliceai-llm-flash/latest"
        assert settings.get("temperature") is None
        assert settings.get("top_p") is None
        assert settings.get("top_k") is None
        assert settings.get("max_tokens") is None
        assert settings["context_window_size"] == 200_000
        assert get_strategy(agent)["strategy_type"] == "DefaultStrategy"
        assert agent["task_profile_id"] is None
