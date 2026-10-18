"""E2E tests: TestUC028_SeedProjectKnowledgeBase.

UC-028: пункт меню 9 «Засеять БЗ ассистентов» (проект + поддержка).

Тесты выполняют реальные эмбеддинги через локальный Ollama, поэтому
пропускаются, если Ollama недоступна.
"""

import pytest
from e2e_helpers import ollama_available, run_cli_command
from ground_truth import get_documents, get_knowledge_base_by_name

from config import PROJECT_KB_NAME, SUPPORT_KB_NAME

pytestmark = pytest.mark.skipif(
    not ollama_available(),
    reason="Ollama недоступна — засев БЗ требует реальных эмбеддингов",
)

TIMEOUT = 900


class TestUC028_SeedProjectKnowledgeBase:
    """TC-159..TC-160: засев баз знаний ассистентов (UC-028)."""

    def test_tc_159_seed_creates_and_indexes(self):
        """TC-159: засев создаёт обе базы и индексирует документацию."""
        test_input = "7\n9\ny\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- ЗАСЕВ БАЗ АССИСТЕНТОВ" in stdout
        project_kb = get_knowledge_base_by_name(PROJECT_KB_NAME)
        assert project_kb is not None
        names = {doc["name"] for doc in get_documents(project_kb["id"])}
        assert "README.md" in names
        assert any(name.endswith(".md") for name in names)

        support_kb = get_knowledge_base_by_name(SUPPORT_KB_NAME)
        assert support_kb is not None
        support_names = {doc["name"] for doc in get_documents(support_kb["id"])}
        assert "faq.md" in support_names

    def test_tc_160_reseed_removes_stale_and_no_duplicates(self):
        """TC-160: повторный засев не оставляет дублей документов."""
        test_input = "7\n9\ny\n9\ny\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "Удалено устаревших документов: 0" in stdout  # first run
        for kb_name in (PROJECT_KB_NAME, SUPPORT_KB_NAME):
            kb = get_knowledge_base_by_name(kb_name)
            assert kb is not None
            names = [doc["name"] for doc in get_documents(kb["id"])]
            assert len(names) == len(set(names))

