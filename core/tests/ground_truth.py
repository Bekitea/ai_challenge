"""Ground truth для e2e-тестов: чтение состояния после прогона CLI.

Тесты проверяют не только вывод программы, но и фактическое состояние данных
(таблицы SQLite и pickle-файлы), которое осталось после пользовательского ввода.
Модуль намеренно работает напрямую с ``sqlite3`` и ``pickle`` — без ORM и
бизнес-логики, — чтобы проверки были независимы от кода приложения.

Все пути берутся из :func:`e2e_helpers.get_test_data_path`, то есть учитывают
изоляцию хранилища по воркерам pytest-xdist.
"""

from __future__ import annotations

import json
import pickle
import sqlite3
from pathlib import Path
from typing import Any

from e2e_helpers import get_test_data_path

# --- Низкоуровневый доступ ---------------------------------------------------


def db_path() -> Path:
    """Путь к SQLite-базе тестового хранилища."""
    return get_test_data_path() / "agents.db"


def file_storage_path() -> Path:
    """Путь к директории файлового хранилища тестов."""
    return get_test_data_path() / "file_storage"


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Выполняет SELECT и возвращает строки (пустой список, если БД нет)."""
    if not db_path().exists():
        return []
    connection = sqlite3.connect(str(db_path()))
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Выполняет SELECT и возвращает первую строку или None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def _load_pickle(path: Path) -> Any | None:
    """Загружает pickle-файл или None, если файла нет."""
    if not path.exists():
        return None
    with open(path, "rb") as handle:
        return pickle.load(handle)


# --- Агенты (чаты) -----------------------------------------------------------


def get_agents() -> list[sqlite3.Row]:
    """Все агенты по возрастанию id."""
    return query("SELECT * FROM agents ORDER BY id")


def get_agent(agent_id: int) -> sqlite3.Row | None:
    """Агент по числовому id."""
    return query_one("SELECT * FROM agents WHERE id = ?", (agent_id,))


def get_agent_by_name(name: str) -> sqlite3.Row | None:
    """Последний созданный агент с указанным именем."""
    return query_one(
        "SELECT * FROM agents WHERE name = ? ORDER BY id DESC", (name,)
    )


def get_last_agent() -> sqlite3.Row | None:
    """Последний созданный агент."""
    return query_one("SELECT * FROM agents ORDER BY id DESC")


def get_settings(agent: sqlite3.Row | None) -> dict:
    """Разбирает ``settings_json`` агента в словарь."""
    if agent is None:
        return {}
    raw = agent["settings_json"]
    return json.loads(raw) if raw else {}


def get_strategy(agent: sqlite3.Row | None) -> dict:
    """Возвращает ``{"strategy_type": ..., **params}`` агента."""
    if agent is None:
        return {}
    params: dict = {}
    raw = agent["strategy_params_json"]
    if raw:
        params = json.loads(raw)
    return {"strategy_type": agent["strategy_type"], **params}


def get_phase(agent: sqlite3.Row | None) -> str | None:
    """Текущая фаза агента (``current_phase``) или None."""
    return agent["current_phase"] if agent is not None else None


def get_phase_by_name(name: str) -> str | None:
    """Текущая фаза агента с указанным именем."""
    return get_phase(get_agent_by_name(name))


def get_agent_profile_id(name: str) -> str | None:
    """id привязанного профиля задачи агента (None, если не привязан)."""
    agent = get_agent_by_name(name)
    return agent["task_profile_id"] if agent is not None else None


def get_mcp_servers(agent: sqlite3.Row | None) -> list[str]:
    """Машинные имена подключённых MCP-серверов агента."""
    if agent is None:
        return []
    raw = agent["mcp_servers_json"]
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(name) for name in data] if isinstance(data, list) else []


def get_mcp_servers_by_name(name: str) -> list[str]:
    """Машинные имена подключённых MCP-серверов агента с указанным именем."""
    return get_mcp_servers(get_agent_by_name(name))


# --- История переписки (файловое хранилище) ---------------------------------


def get_history(conversation_id: str) -> list:
    """Список объектов ``Prompt`` из файла истории (или пустой список)."""
    return _load_pickle(file_storage_path() / f"{conversation_id}.pkl") or []


def get_history_by_name(name: str) -> list:
    """История агента с указанным именем."""
    agent = get_agent_by_name(name)
    return get_history(agent["conversation_id"]) if agent else []


def get_messages(conversation_id: str) -> list[dict]:
    """Упрощённое представление истории: role/content/is_remembered."""
    return [
        {
            "role": prompt.role,
            "content": prompt.content,
            "reasoning": getattr(prompt, "reasoning", None),
            "is_remembered": getattr(prompt, "is_remembered", None),
            "tool_calls": getattr(prompt, "tool_calls", None),
        }
        for prompt in get_history(conversation_id)
    ]


def get_messages_by_name(name: str) -> list[dict]:
    """Упрощённая история агента с указанным именем."""
    agent = get_agent_by_name(name)
    return get_messages(agent["conversation_id"]) if agent else []


# --- Глобальная и задача-память ---------------------------------------------


def get_global_memory():
    """Объект ``GlobalMemory`` (или None)."""
    return _load_pickle(get_test_data_path() / "global_memory.pkl")


def get_global_facts() -> list[str]:
    """Список фактов глобальной памяти."""
    memory = get_global_memory()
    return list(getattr(memory, "facts", []) or []) if memory else []


def get_task_memory(conversation_id: str):
    """Объект ``TaskMemory`` диалога (или None)."""
    return _load_pickle(file_storage_path() / "task_memory" / f"{conversation_id}.pkl")


def get_task_memory_by_name(name: str):
    """Память задачи агента с указанным именем."""
    agent = get_agent_by_name(name)
    return get_task_memory(agent["conversation_id"]) if agent else None


# --- Профили задач -----------------------------------------------------------


def get_task_profiles() -> list[sqlite3.Row]:
    """Все профили задач по дате создания."""
    return query("SELECT * FROM task_profiles ORDER BY created_at, id")


def get_profile_by_name(name: str) -> sqlite3.Row | None:
    """Последний профиль с указанным именем."""
    return query_one(
        "SELECT * FROM task_profiles WHERE name = ? ORDER BY created_at DESC", (name,)
    )


def get_profile_facts(profile_id: str) -> list[str]:
    """Факты профиля из файла ``<profile_id>.pkl``."""
    return _load_pickle(file_storage_path() / f"{profile_id}.pkl") or []


def get_invariants(profile_id: str) -> list[sqlite3.Row]:
    """Инварианты профиля по дате создания."""
    return query(
        "SELECT * FROM task_profile_invariants WHERE profile_id = ? "
        "ORDER BY created_at, id",
        (profile_id,),
    )


# --- API-ключи ---------------------------------------------------------------


def get_api_keys() -> list[sqlite3.Row]:
    """Все API-ключи по возрастанию id."""
    return query("SELECT * FROM api_keys ORDER BY id")


# --- RAG (базы знаний) -------------------------------------------------------


def get_knowledge_bases() -> list[sqlite3.Row]:
    """Все базы знаний."""
    return query("SELECT * FROM knowledge_bases ORDER BY id")


def get_knowledge_base_by_name(name: str) -> sqlite3.Row | None:
    """База знаний по имени."""
    return query_one("SELECT * FROM knowledge_bases WHERE name = ? ORDER BY id DESC", (name,))


def get_documents(kb_id: int) -> list[sqlite3.Row]:
    """Документы базы знаний."""
    return query("SELECT * FROM documents WHERE kb_id = ? ORDER BY id", (kb_id,))


def get_chunks(document_id: int) -> list[sqlite3.Row]:
    """Чанки документа по порядку."""
    return query(
        "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
        (document_id,),
    )


def get_agent_knowledge_bases(agent_id: int) -> list[sqlite3.Row]:
    """Привязки агента к базам знаний."""
    return query(
        "SELECT * FROM agent_knowledge_bases WHERE agent_id = ? ORDER BY id",
        (agent_id,),
    )


# --- Научная библиотека (research) -------------------------------------------


def get_research_libraries() -> list[sqlite3.Row]:
    """Все научные библиотеки."""
    return query("SELECT * FROM research_libraries ORDER BY id")


def get_research_library_by_name(name: str) -> sqlite3.Row | None:
    """Научная библиотека по имени."""
    return query_one(
        "SELECT * FROM research_libraries WHERE name = ? ORDER BY id DESC", (name,)
    )


def get_agent_research_library(agent_id: int) -> sqlite3.Row | None:
    """Активная научная библиотека чата."""
    link = query_one(
        "SELECT * FROM agent_research_libraries WHERE agent_id = ?", (agent_id,)
    )
    if link is None:
        return None
    return query_one(
        "SELECT * FROM research_libraries WHERE id = ?", (link["library_id"],)
    )


def get_research_articles(library_id: int) -> list[sqlite3.Row]:
    """Статьи научной библиотеки."""
    return query(
        "SELECT * FROM research_articles WHERE library_id = ? ORDER BY id",
        (library_id,),
    )
