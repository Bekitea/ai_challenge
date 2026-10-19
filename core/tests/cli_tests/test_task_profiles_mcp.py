"""E2E: MCP-серверы в профилях задачи и автоподключение при создании чата."""

import json

from e2e_helpers import run_cli_command
from ground_truth import get_mcp_servers_by_name, get_profile_by_name


class TestTaskProfilesMcp:
    """Профили задачи: настройка MCP и быстрое создание чата с профилем."""

    def test_create_profile_with_mcp_server(self):
        """Профиль создаётся с выбранным MCP-сервером (time)."""
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "MCP Profile\n"
            "Profile with MCP\n"
            "\n"  # Предпочтения
            "\n"  # Инварианты
            "3\n"  # MCP: time (реестр: openalex, research, time, ...)
            "3\n"  # Назад в главное меню
            "8\n"
        )

        _, _, _ = run_cli_command(test_input, timeout=120)

        profile = get_profile_by_name("MCP Profile")
        assert profile is not None
        assert json.loads(profile["mcp_servers_json"]) == ["time"]

    def test_quick_chat_with_profile_connects_its_mcp(self):
        """«Создать чат с этим профилем» подключает MCP профиля."""
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Chat With MCP\n"
            "Profile for quick chat\n"
            "\n"  # Предпочтения
            "\n"  # Инварианты
            "3\n"  # MCP: time
            "2\n"  # Список профилей
            "4\n"  # Создать чат с этим профилем
            "1\n"  # Профиль №1
            "MCP Chat\n"  # Имя чата
            "1\n"  # Модель
            "\n"  # Reasoning effort (по умолчанию)
            "/menu\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=180)

        assert "[OK] Чат 'MCP Chat' создан с профилем 'Chat With MCP'." in stdout
        assert get_mcp_servers_by_name("MCP Chat") == ["time"]

    def test_configure_profile_mcp_after_creation(self):
        """MCP-серверы профиля можно изменить после создания."""
        test_input = (
            "3\n"  # Профили задач
            "1\n"  # Создать профиль
            "Editable MCP\n"
            "Profile to edit\n"
            "\n"  # Предпочтения
            "\n"  # Инварианты
            "\n"  # MCP: без серверов
            "2\n"  # Список профилей
            "5\n"  # Настроить MCP-серверы
            "1\n"  # Профиль №1
            "3\n"  # MCP: time
            "3\n"  # Назад в главное меню
            "8\n"
        )

        _, _, _ = run_cli_command(test_input, timeout=120)

        profile = get_profile_by_name("Editable MCP")
        assert profile is not None
        assert json.loads(profile["mcp_servers_json"]) == ["time"]
