"""E2E tests: TestUC028_SeedProjectKnowledgeBase.

UC-028: пункт меню «Засеять проектную БЗ» (README + docs).

Тесты выполняют реальные эмбеддинги через локальный Ollama, поэтому
пропускаются, если Ollama недоступна.
"""

import pytest
from e2e_helpers import ollama_available, run_cli_command
from ground_truth import get_documents, get_knowledge_base_by_name

from config import PROJECT_KB_NAME

pytestmark = pytest.mark.skipif(
    not ollama_available(),
    reason="Ollama недоступна — засев проектной БЗ требует реальных эмбеддингов",
)

TIMEOUT = 600


class TestUC028_SeedProjectKnowledgeBase:
    """TC-159..TC-160: засев проектной базы знаний (UC-028)."""

    def test_tc_159_seed_creates_and_indexes(self):
        """TC-159: засев создаёт базу и индексирует README/docs проекта."""
        test_input = "7\n9\ny\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- ЗАСЕВ ПРОЕКТНОЙ БАЗЫ" in stdout
        kb = get_knowledge_base_by_name(PROJECT_KB_NAME)
        assert kb is not None
        names = {doc["name"] for doc in get_documents(kb["id"])}
        assert "README.md" in names
        assert any(name.endswith(".md") for name in names)

    def test_tc_160_reseed_removes_stale_and_no_duplicates(self):
        """TC-160: повторный засев не оставляет дублей документов."""
        test_input = "7\n9\ny\n9\ny\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "Удалено устаревших документов: 0" in stdout  # first run
        kb = get_knowledge_base_by_name(PROJECT_KB_NAME)
        assert kb is not None
        names = [doc["name"] for doc in get_documents(kb["id"])]
        assert len(names) == len(set(names))
