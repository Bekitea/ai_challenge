"""E2E tests: TestUC020_RagKnowledgeBases.

UC-020: локальная RAG-подсистема (базы знаний, документы, чанки, RAG-поиск).

Тесты выполняют реальные эмбеддинги через локальный Ollama, поэтому
пропускаются, если Ollama недоступна.
"""

import pytest
from e2e_helpers import _QUICK_CHAT, ollama_available, run_cli_command

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
        test_input = "7\n1\nTest KB\nОписание базы\n0\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[OK] База знаний 'Test KB' создана!" in stdout
        assert "Модель эмбеддинга: bge-m3 (1024)" in stdout

    def test_tc_122_create_knowledge_base_empty_name(self):
        """TC-122: Пустое название базы знаний -> ошибка и повторный ввод."""
        test_input = "7\n1\n\nTest KB2\n\n0\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[ERROR] Название базы знаний не может быть пустым." in stdout
        assert "[OK] База знаний 'Test KB2' создана!" in stdout

    def test_tc_123_list_knowledge_bases(self):
        """TC-123: Список баз знаний возвращает корректные данные."""
        test_input = (
            "7\n"
            "1\nAlpha\n\n"
            "1\nBeta\n\n"
            "2\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- СПИСОК БАЗ ЗНАНИЙ ---" in stdout
        assert "1. Alpha" in stdout
        assert "2. Beta" in stdout
        assert "Документов: 0 | Чанков: 0" in stdout

    def test_tc_124_add_document_and_list_documents(self, doc_file):
        """TC-124/125: Добавление документа создаёт чанки, документ = ready."""
        test_input = (
            "7\n"
            "1\nKB Docs\n\n"
            f"3\n1\n{doc_file}\n"
            "4\n1\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[OK] france.txt — чанков:" in stdout
        assert "Документы БАЗЫ 'KB Docs'".lower() in stdout.lower()
        assert "[ready]" in stdout

    def test_tc_125_list_document_chunks(self, doc_file):
        """TC-125: Просмотр чанков документа в правильном порядке."""
        test_input = (
            "7\n"
            "1\nKB Chunks\n\n"
            f"3\n1\n{doc_file}\n"
            "5\n1\n1\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- ЧАНКИ ДОКУМЕНТА 'france.txt' ---" in stdout
        assert "[0] (id=" in stdout
        assert "Столица Франции" in stdout

    def test_tc_126_attach_and_detach_knowledge_base(self):
        """TC-126: Подключение и отключение базы знаний к чату через /rag."""
        test_input = (
            "7\n1\nKB Chat\n\n0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "/rag\n2\n1\n"
            + "/menu\n6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "--- БАЗЫ ЗНАНИЙ ЧАТА: Чат 1 ---" in stdout
        assert "База знаний 'KB Chat' подключена к чату." in stdout
        assert "База знаний 'KB Chat' отключена от чата." in stdout

    def test_tc_127_search_knowledge_base(self, doc_file):
        """TC-127: Поиск по базе знаний возвращает релевантный чанк."""
        test_input = (
            "7\n"
            "1\nKB Search\n\n"
            f"3\n1\n{doc_file}\n"
            "8\n1\nГде находится Эйфелева башня?\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "--- РЕЗУЛЬТАТЫ ПОИСКА (база 'KB Search') ---" in stdout
        assert "france.txt" in stdout
        assert "Столица Франции" in stdout

    def test_tc_128_rag_context_used_in_dialog(self, doc_file):
        """TC-128: При подключённой базе знаний диалог продолжается с RAG."""
        test_input = (
            "7\n1\nKB Dialog\n\n"
            f"3\n1\n{doc_file}\n"
            "0\n"
            + _QUICK_CHAT
            + "/rag\n1\n1\n"
            + "Где находится Эйфелева башня?\n\n"
            + "/menu\n6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "База знаний 'KB Dialog' подключена к чату." in stdout
        assert "[AGENT]: [MOCK RESPONSE]" in stdout

    def test_tc_129_dialog_without_knowledge_base(self):
        """TC-129: Без подключённых баз знаний диалог идёт без RAG-ошибок."""
        test_input = _QUICK_CHAT + "Обычное сообщение\n\n" + "/menu\n6\n"

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
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[OK] Документ 'france.txt' удалён." in stdout
        assert "нет документов" in stdout

    def test_tc_131_delete_knowledge_base(self):
        """TC-131: Удаление базы знаний удаляет её из списка."""
        test_input = (
            "7\n"
            "1\nKB Del\n\n"
            "7\n1\ny\n"
            "2\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input)

        assert "[OK] База знаний 'KB Del' удалена." in stdout
        assert "Базы знаний отсутствуют." in stdout

    def test_tc_132_add_document_missing_path(self):
        """TC-132: Несуществующий путь -> понятная ошибка, без падения."""
        test_input = "7\n1\nKB Err\n\n3\n1\n/no/such/path.txt\n0\n6\n"

        stdout, _, _ = run_cli_command(test_input)

        assert "[ERROR]" in stdout
        assert "не найден" in stdout

    def test_tc_133_add_python_file_document(self, py_file):
        """TC-133: .py-файл добавляется как документ и индексируется."""
        test_input = (
            "7\n"
            "1\nKB Python\n\n"
            f"3\n1\n{py_file}\n"
            "4\n1\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[OK] sample.py — чанков:" in stdout
        assert "sample.py" in stdout
        assert "[ready]" in stdout

    def test_tc_134_empty_files_are_skipped(self, mixed_folder):
        """TC-134: Пустые файлы пропускаются, а не прерывают индексацию."""
        test_input = (
            "7\n"
            "1\nKB Skip\n\n"
            f"3\n1\n{mixed_folder}\n"
            "4\n1\n"
            "0\n"
            "6\n"
        )

        stdout, _, _ = run_cli_command(test_input, timeout=TIMEOUT)

        assert "[OK] notes.txt — чанков:" in stdout
        assert "empty.py" not in stdout
        assert "[ERROR]" not in stdout
        assert "[ready]" in stdout
