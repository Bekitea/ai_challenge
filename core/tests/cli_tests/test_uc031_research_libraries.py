"""E2E tests: UC-031 — научные библиотеки, привязанные к чатам.

Проверяется, что research MCP-сервер подключается из чата, инструмент получает
контекст чата (AI_CHAT_AGENT_ID) и создаёт/использует собственную библиотеку.
Сеть не требуется: вызывается только локальный инструмент без внешних запросов.
"""

from e2e_helpers import _QUICK_CHAT, run_cli_command
from ground_truth import (
    get_agent_by_name,
    get_agent_research_library,
    get_knowledge_bases,
    get_research_libraries,
    get_research_library_by_name,
)

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.infrastructure.mcp.mcp_registry import get_available_servers
from core.infrastructure.persistence.db_connection import DatabaseConnection
from core.infrastructure.persistence.orm import Base
from core.infrastructure.persistence.sqlite_research_article_repository import (
    SqliteResearchArticleRepository,
)

_STATS_TOOL = {
    "responses": [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "1",
                    "name": "research__get_library_stats",
                    "arguments": "{}",
                }
            ],
        },
        {"content": "Статистика библиотеки готова."},
    ],
    "default": {"content": "[MOCK RESPONSE]"},
}


class TestUC031_ResearchLibraries:
    """TC-167..TC-170: research MCP и библиотека на чат (UC-031)."""

    def test_tc_167_research_server_is_registered(self):
        """TC-167: research-сервер доступен в реестре MCP."""
        names = {server.name for server in get_available_servers()}
        assert "research" in names

    def test_tc_168_connect_research_mcp_creates_chat_library(self):
        """TC-168: подключение research MCP и вызов инструмента создаёт библиотеку чата."""
        test_input = (
            _QUICK_CHAT
            + "/mcp\ny\nresearch\n"
            + "Сделай статистику библиотеки\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, mock=_STATS_TOOL, timeout=120)

        assert "[OK] MCP 'Research Library'" in stdout
        assert "[AGENT]: Статистика библиотеки готова." in stdout

        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        library = get_agent_research_library(agent["id"])
        assert library is not None
        assert "Чат 1" in library["name"]

        libraries = get_research_libraries()
        assert len(libraries) >= 1
        assert library["knowledge_base_id"] is not None

        knowledge_bases = {
            row["id"]: row["name"] for row in get_knowledge_bases()
        }
        kb_name = knowledge_bases.get(library["knowledge_base_id"], "")
        assert "Научная библиотека" in kb_name

    def test_tc_169_two_chats_get_separate_libraries(self):
        """TC-169: два чата в одной сессии получают разные библиотеки и БЗ."""
        test_input = (
            _QUICK_CHAT
            + "/mcp\ny\nresearch\n"
            + "статистика первого чата\n"
            + "/menu\n"
            + "1\n\n3\n\n"
            + "/mcp\ny\nresearch\n"
            + "статистика второго чата\n"
            + "/menu\n8\n"
        )
        mock = {
            "responses": [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "1",
                            "name": "research__get_library_stats",
                            "arguments": "{}",
                        }
                    ],
                },
                {"content": "Готово 1"},
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "2",
                            "name": "research__get_library_stats",
                            "arguments": "{}",
                        }
                    ],
                },
                {"content": "Готово 2"},
            ],
            "default": {"content": "[MOCK RESPONSE]"},
        }

        run_cli_command(test_input, mock=mock, timeout=180)

        first = get_agent_by_name("Чат 1")
        second = get_agent_by_name("Чат 2")
        assert first is not None and second is not None

        library_1 = get_agent_research_library(first["id"])
        library_2 = get_agent_research_library(second["id"])
        assert library_1 is not None and library_2 is not None
        assert library_1["id"] != library_2["id"]
        assert library_1["knowledge_base_id"] != library_2["knowledge_base_id"]

    def test_tc_170_research_tool_without_chat_context_reports_error(self):
        """TC-170: прямой вызов research-инструмента без AI_CHAT_AGENT_ID даёт ошибку."""
        # Проверяется на уровне MCP-сервера в mcp/tests/test_research_mcp.py;
        # здесь фиксируем, что CLI подключает сервер и не падает без вызова.
        test_input = _QUICK_CHAT + "/mcp\ny\nresearch\n/menu\n8\n"

        stdout, _, _ = run_cli_command(test_input, timeout=120)

        assert "[OK] MCP 'Research Library'" in stdout

    def test_tc_171_library_command_create_info_detach(self):
        """TC-171: /library создаёт библиотеку, показывает её и открепляет."""
        test_input = (
            _QUICK_CHAT
            + "/library create Test Library\n"
            + "Цель диссертации\n"
            + "machine learning\n"
            + "RAG, retrieval\n"
            + "2020-2026\n"
            + "/library info\n"
            + "/library detach\n"
            + "/library list\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=120)

        assert "[OK] Научная библиотека 'Test Library' создана" in stdout
        assert "Активная: Test Library" in stdout
        assert "откреплена от чата" in stdout
        assert "Test Library" in stdout

        library = get_research_library_by_name("Test Library")
        assert library is not None
        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        assert get_agent_research_library(agent["id"]) is None

    def test_tc_172_library_can_be_shared_between_chats(self):
        """TC-172: одна научная библиотека подключается к двум чатам."""
        test_input = (
            _QUICK_CHAT
            + "/library create Shared Library\n\n\n\n\n"
            + "/menu\n"
            + "1\n\n3\n\n"
            + "/library use Shared Library\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=120)

        first = get_agent_by_name("Чат 1")
        second = get_agent_by_name("Чат 2")
        assert first is not None and second is not None
        library_1 = get_agent_research_library(first["id"])
        library_2 = get_agent_research_library(second["id"])
        assert library_1 is not None and library_2 is not None
        assert library_1["id"] == library_2["id"]
        assert "Научная библиотека 'Shared Library' подключена" in stdout

    def test_tc_173_branch_inherits_research_library(self):
        """TC-173: ветка чата наследует библиотеку и её БЗ."""
        test_input = (
            _QUICK_CHAT
            + "/library create Branch Library\n\n\n\n\n"
            + "/branch\nBranch test\nn\n"
            + "/library info\n"
            + "/menu\n8\n"
        )

        _, _, _ = run_cli_command(test_input, timeout=120)

        parent = get_agent_by_name("Чат 1")
        branch = get_agent_by_name("Branch test")
        assert parent is not None and branch is not None
        parent_library = get_agent_research_library(parent["id"])
        branch_library = get_agent_research_library(branch["id"])
        assert parent_library is not None and branch_library is not None
        assert parent_library["id"] == branch_library["id"]

    def test_tc_175_library_articles_listing(self):
        """TC-175: /library articles показывает статьи библиотеки и фильтры."""
        run_cli_command(
            _QUICK_CHAT
            + "/library create Glaucoma Library\n\n\n\n\n"
            + "/menu\n8\n",
            timeout=120,
        )
        library = get_research_library_by_name("Glaucoma Library")
        assert library is not None

        db = DatabaseConnection()
        db.init_tables(Base.metadata)
        repository = SqliteResearchArticleRepository(db.get_session)
        repository.upsert(
            library["id"],
            ArticleCandidateDTO(
                title="Glaucoma paper: OCT and deep learning",
                doi="10.77/demo",
                authors=["A. Author", "B. Author"],
                publication_year=2024,
                abstract="Early glaucoma detection",
            ),
            "indexed",
        )
        db.close()

        stdout, _, _ = run_cli_command(
            _QUICK_CHAT
            + "/library use Glaucoma Library\n"
            + "/library articles\n"
            + "/library articles --status abstract_only\n"
            + "/menu\n8\n",
            timeout=120,
        )

        assert "--- Статьи библиотеки: Glaucoma Library ---" in stdout
        assert "Glaucoma paper: OCT and deep learning" in stdout
        assert "[indexed]" in stdout
        assert "Показано: 1 из 1" in stdout
        assert "статей по заданным условиям не найдено" in stdout

    def test_tc_174_library_delete_requires_name_confirmation(self):
        """TC-174: /library delete удаляет библиотеку после подтверждения."""
        test_input = (
            _QUICK_CHAT
            + "/library create Delete Library\n\n\n\n\n"
            + "/library delete Delete Library\n"
            + "Delete Library\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=120)

        assert "Научная библиотека 'Delete Library' удалена" in stdout
        assert get_research_library_by_name("Delete Library") is None
