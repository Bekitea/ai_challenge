"""E2E tests: TestUC020_RagKnowledgeBases.

UC-020: локальная RAG-подсистема (базы знаний, документы, чанки, RAG-поиск).

Тесты выполняют реальные эмбеддинги через локальный Ollama, поэтому
пропускаются, если Ollama недоступна.
"""

import pytest
from e2e_helpers import _QUICK_CHAT, ollama_available, run_cli_command
from ground_truth import (
    get_agent_by_name,
    get_agent_knowledge_bases,
    get_chunks,
    get_documents,
    get_knowledge_base_by_name,
)

pytestmark = pytest.mark.skipif(
    not ollama_available(),
    reason="Ollama недоступна — RAG-эмбеддинги требуют реального провайдера",
)

DOC_TEXT = (
    "Столица Франции — Париж. Эйфелева башня находится в Париже. "
    "Франция расположена в Западной Европе. "
) * 20

TIMEOUT = 120


@pytest.fixture
def doc_file(tmp_path):
    path = tmp_path / "france.txt"
    path.write_text(DOC_TEXT, encoding="utf-8")
    return str(path)


@pytest.fixture
def py_file(tmp_path):
    path = tmp_path / "sample.py"
    path.write_text(
        '"""Модуль приветствия."""\n\n\n'
        "def greet(name: str) -> str:\n"
        '    """Возвращает приветствие для указанного имени."""\n'
        '    return f"Hello, {name}!"\n\n\n'
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def mixed_folder(tmp_path):
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    (tmp_path / "notes.txt").write_text(DOC_TEXT, encoding="utf-8")
    return str(tmp_path)


class TestUC020_RagKnowledgeBases:
    """TC-121..TC-132: базы знаний и RAG (UC-020)."""

    def test_tc_121_create_knowledge_base(self):
        """TC-121: Создание базы знаний (UC-020 main success)."""
        test_input = "7\n1\nTest KB\nОписание базы\n0\n8\n"

        run_cli_command(test_input)

        kb = get_knowledge_base_by_name("Test KB")
        assert kb is not None
        assert kb["embedding_model"] == "bge-m3"
        assert kb["embedding_dimension"] == 1024
        assert kb["description"] == "Описание базы"

    def test_tc_122_create_knowledge_base_empty_name(self):
        """TC-122: Пустое название базы знаний -> ошибка и повторный ввод."""
        test_input = "7\n1\n\nTest KB2\n\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[ERROR] Название базы знаний не может быть пустым." in stdout
        assert "[OK] База знаний 'Test KB2' создана!" in stdout
        assert get_knowledge_base_by_name("Test KB2") is not None

    def test_tc_123_list_knowledge_bases(self):
        """TC-123: Список баз знаний возвращает корректные данные."""
        test_input = (
            "7\n"
            "1\nAlpha\n\n"
            "1\nBeta\n\n"
            "2\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- СПИСОК БАЗ ЗНАНИЙ ---" in stdout
        # Ground truth: обе базы созданы и пусты
        alpha = get_knowledge_base_by_name("Alpha")
        beta = get_knowledge_base_by_name("Beta")
        assert alpha is not None and beta is not None
        assert get_documents(alpha["id"]) == []
        assert get_documents(beta["id"]) == []

    def test_tc_124_add_document_and_list_documents(self, doc_file):
        """TC-124/125: Добавление документа создаёт чанки, документ = ready."""
        test_input = (
            "7\n"
            "1\nKB Docs\n\n"
            f"3\n1\n{doc_file}\n"
            "4\n1\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "Документы БАЗЫ 'KB Docs'".lower() in stdout.lower()
        kb = get_knowledge_base_by_name("KB Docs")
        assert kb is not None
        documents = get_documents(kb["id"])
        assert len(documents) == 1
        assert documents[0]["name"] == "france.txt"
        assert documents[0]["status"] == "ready"
        assert documents[0]["chunk_count"] > 0
        assert len(get_chunks(documents[0]["id"])) == documents[0]["chunk_count"]

    def test_tc_125_list_document_chunks(self, doc_file):
        """TC-125: Просмотр чанков документа в правильном порядке."""
        test_input = (
            "7\n"
            "1\nKB Chunks\n\n"
            f"3\n1\n{doc_file}\n"
            "5\n1\n1\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- ЧАНКИ ДОКУМЕНТА 'france.txt' ---" in stdout
        kb = get_knowledge_base_by_name("KB Chunks")
        assert kb is not None
        chunks = get_chunks(get_documents(kb["id"])[0]["id"])
        assert chunks
        assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
        assert "Столица Франции" in chunks[0]["text"]

    def test_tc_126_attach_and_detach_knowledge_base(self):
        """TC-126: Подключение и отключение базы знаний к чату через /rag."""
        test_input = (
            "7\n1\nKB Chat\n\n0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "/rag\n2\n1\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- БАЗЫ ЗНАНИЙ ЧАТА: Чат 1 ---" in stdout
        assert "База знаний 'KB Chat' подключена к чату." in stdout
        assert "База знаний 'KB Chat' отключена от чата." in stdout
        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        # После отсоединения связей чата с базами знаний не осталось
        assert get_agent_knowledge_bases(agent["id"]) == []

    def test_tc_127_search_knowledge_base(self, doc_file):
        """TC-127: Поиск по базе знаний возвращает релевантный чанк."""
        test_input = (
            "7\n"
            "1\nKB Search\n\n"
            f"3\n1\n{doc_file}\n"
            "8\n1\nГде находится Эйфелева башня?\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- РЕЗУЛЬТАТЫ ПОИСКА (база 'KB Search') ---" in stdout
        # Ground truth: документ и его текст сохранены в базе
        kb = get_knowledge_base_by_name("KB Search")
        assert kb is not None
        documents = get_documents(kb["id"])
        assert [d["name"] for d in documents] == ["france.txt"]
        assert "Столица Франции" in get_chunks(documents[0]["id"])[0]["text"]

    def test_tc_128_rag_context_used_in_dialog(self, doc_file):
        """TC-128: При подключённой базе знаний диалог продолжается с RAG."""
        test_input = (
            "7\n1\nKB Dialog\n\n"
            f"3\n1\n{doc_file}\n"
            "0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "Где находится Эйфелева башня?\n\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        # Ground truth: база знаний подключена к чату
        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        assert len(get_agent_knowledge_bases(agent["id"])) == 1

    def test_tc_129_dialog_without_knowledge_base(self):
        """TC-129: Без подключённых баз знаний диалог идёт без RAG-ошибок."""
        test_input = _QUICK_CHAT + "Обычное сообщение\n" + "/menu\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "[ERROR]" not in stdout

    def test_tc_130_delete_document(self, doc_file):
        """TC-130: Удаление документа удаляет его из базы знаний."""
        test_input = (
            "7\n"
            "1\nKB DelDoc\n\n"
            f"3\n1\n{doc_file}\n"
            "6\n1\n1\ny\n"
            "4\n1\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "нет документов" in stdout
        kb = get_knowledge_base_by_name("KB DelDoc")
        assert kb is not None
        assert get_documents(kb["id"]) == []

    def test_tc_131_delete_knowledge_base(self):
        """TC-131: Удаление базы знаний удаляет её из списка."""
        test_input = (
            "7\n"
            "1\nKB Del\n\n"
            "7\n1\ny\n"
            "2\n"
            "0\n"
            "8\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "Базы знаний отсутствуют." in stdout
        assert get_knowledge_base_by_name("KB Del") is None

    def test_tc_132_add_document_missing_path(self):
        """TC-132: Несуществующий путь -> понятная ошибка, без падения."""
        test_input = "7\n1\nKB Err\n\n3\n1\n/no/such/path.txt\n0\n8\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "не найден" in stdout
        # Ground truth: документ не добавлен
        kb = get_knowledge_base_by_name("KB Err")
        assert kb is not None
        assert get_documents(kb["id"]) == []

    def test_tc_133_add_python_file_document(self, py_file):
        """TC-133: .py-файл добавляется как документ и индексируется."""
        test_input = (
            "7\n"
            "1\nKB Python\n\n"
            f"3\n1\n{py_file}\n"
            "4\n1\n"
            "0\n"
            "8\n"
        )

        run_cli_command(test_input, timeout=TIMEOUT)

        kb = get_knowledge_base_by_name("KB Python")
        assert kb is not None
        documents = get_documents(kb["id"])
        assert [d["name"] for d in documents] == ["sample.py"]
        assert documents[0]["status"] == "ready"
        assert documents[0]["chunk_count"] > 0

    def test_tc_134_empty_files_are_skipped(self, mixed_folder):
        """TC-134: Пустые файлы пропускаются, а не прерывают индексацию."""
        test_input = (
            "7\n"
            "1\nKB Skip\n\n"
            f"3\n1\n{mixed_folder}\n"
            "4\n1\n"
            "0\n"
            "8\n"
        )

        run_cli_command(test_input, timeout=TIMEOUT)

        kb = get_knowledge_base_by_name("KB Skip")
        assert kb is not None
        assert [d["name"] for d in get_documents(kb["id"])] == ["notes.txt"]

    def test_tc_139_rag_sources_shown_in_dialog(self, doc_file):
        """TC-139: При подключённой базе знаний после ответа печатаются источники."""
        test_input = (
            "7\n1\nKB Sources\n\n"
            f"3\n1\n{doc_file}\n"
            "0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "Где находится Эйфелева башня?\n\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        # UI: источники печатаются после ответа
        assert "[Источники]:" in stdout
        assert "france.txt — чанк #" in stdout
        # Ground truth: база знаний подключена к чату
        agent = get_agent_by_name("Чат 1")
        assert agent is not None
        assert len(get_agent_knowledge_bases(agent["id"])) == 1

    def test_tc_140_rag_below_threshold_reports_no_sources(self, doc_file, monkeypatch):
        """TC-140: Порог релевантности выше любого score -> источников нет."""
        monkeypatch.setenv("RAG_RELEVANCE_THRESHOLD", "1.1")
        test_input = (
            "7\n1\nKB Threshold\n\n"
            f"3\n1\n{doc_file}\n"
            "0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "Где находится Эйфелева башня?\n\n"
            + "/menu\n8\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[AGENT]: [MOCK RESPONSE]" in stdout
        assert "релевантных фрагментов не найдено" in stdout
