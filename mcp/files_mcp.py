#!/usr/bin/env python3
"""MCP-сервер работы с файлами проекта.

Позволяет ассистенту читать, искать и изменять файлы внутри корня проекта.
Все операции ограничены корнем репозитория, файлы ``.env*`` запрещены, бинарные
и слишком большие файлы не читаются.

Запись двухшаговая: по умолчанию инструменты записи (``write_file``,
``replace_in_file``) не меняют файл, а возвращают preview-diff (``apply=False``).
Чтобы применить изменение, инструмент нужно вызвать повторно с ``apply=True``.

Корень рабочего пространства по умолчанию — каталог проекта; его можно
переопределить переменной окружения ``PROJECT_FILES_ROOT`` (используется в
e2e-тестах, чтобы не менять реальный репозиторий).
"""

from __future__ import annotations

import difflib
import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from mcp.server import MCPServer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Корень можно переопределить (например, для e2e-тестов записи, чтобы не
# менять реальный репозиторий).
DEFAULT_PROJECT_ROOT = PROJECT_ROOT

# Лимит на чтение/поиск/запись одного файла (по умолчанию 256 КБ).
DEFAULT_MAX_BYTES = 256 * 1024
# Ограничения размера вывода инструментов, чтобы не переполнять контекст LLM.
MAX_LIST_RESULTS = 500
MAX_SEARCH_MATCHES = 100
MAX_OUTPUT_CHARS = 20000

# Каталоги, которые не просматриваются и не индексируются.
DEFAULT_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
}

mcp = MCPServer(
    "ProjectFiles",
    description="Чтение, поиск и изменение файлов внутри проекта.",
)


def _max_bytes() -> int:
    raw = os.getenv("PROJECT_FILES_MAX_BYTES")
    try:
        value = int(raw) if raw else DEFAULT_MAX_BYTES
    except ValueError:
        value = DEFAULT_MAX_BYTES
    return value if value > 0 else DEFAULT_MAX_BYTES


def _root() -> Path:
    """Возвращает корень рабочего пространства (env ``PROJECT_FILES_ROOT``)."""
    raw = os.getenv("PROJECT_FILES_ROOT")
    return Path(raw).resolve() if raw else DEFAULT_PROJECT_ROOT


def _resolve(path: str, *, allow_missing: bool = False) -> Path:
    """Разрешает путь и проверяет, что он внутри корня проекта."""
    root = _root()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Путь '{path}' выходит за пределы корня проекта.")
    if not allow_missing and not candidate.exists():
        raise ValueError(f"Путь '{path}' не найден.")
    return candidate


def _is_forbidden(path: Path) -> bool:
    """Запрещает доступ к файлам с секретами (.env*)."""
    name = path.name
    return name == ".env" or name.startswith(".env")


def _load_gitignore(root: Path) -> list[tuple[str, bool, bool]]:
    """Читает .gitignore и возвращает (pattern, dir_only, anchored)."""
    gitignore = root / ".gitignore"
    patterns: list[tuple[str, bool, bool]] = []
    if not gitignore.is_file():
        return patterns
    try:
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return patterns

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        dir_only = stripped.endswith("/")
        anchored = stripped.startswith("/")
        pattern = stripped.strip("/")
        if pattern:
            patterns.append((pattern, dir_only, anchored))
    return patterns


_GITIGNORE_CACHE: dict[Path, list[tuple[str, bool, bool]]] = {}


def _gitignore_for(root: Path) -> list[tuple[str, bool, bool]]:
    """Возвращает правила .gitignore для корня (с кэшем по корню)."""
    if root not in _GITIGNORE_CACHE:
        _GITIGNORE_CACHE[root] = _load_gitignore(root)
    return _GITIGNORE_CACHE[root]


def _matches_ignored(
    rel_posix: str, name: str, patterns: list[tuple[str, bool, bool]]
) -> bool:
    parts = rel_posix.split("/")
    for pattern, _dir_only, anchored in patterns:
        if anchored:
            if rel_posix == pattern or fnmatch.fnmatch(rel_posix, pattern):
                return True
            continue
        if fnmatch.fnmatch(name, pattern):
            return True
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def _is_ignored(
    rel_posix: str, name: str, patterns: list[tuple[str, bool, bool]]
) -> bool:
    if any(part in DEFAULT_IGNORED_DIRS for part in rel_posix.split("/")):
        return True
    return _matches_ignored(rel_posix, name, patterns)


def _walk_files(base: Path, patterns: list[tuple[str, bool, bool]]) -> Iterator[Path]:
    """Обходит файлы, пропуская игнорируемые каталоги (без спуска внутрь)."""
    root = _root()
    stack = [base]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            try:
                rel = entry.relative_to(root).as_posix()
            except ValueError:
                continue
            if entry.is_dir():
                if _is_ignored(rel, entry.name, patterns):
                    continue
                stack.append(entry)
            elif entry.is_file():
                yield entry


def _rel(path: Path) -> str:
    return path.relative_to(_root()).as_posix()


def _read_bytes(path: Path) -> bytes:
    if _is_forbidden(path):
        raise ValueError(f"Доступ к файлу '{path.name}' запрещён.")
    size = path.stat().st_size
    limit = _max_bytes()
    if size > limit:
        raise ValueError(
            f"Файл '{_rel(path)}' слишком большой ({size} байт, лимит {limit})."
        )
    return path.read_bytes()


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data


def _read_text(path: Path) -> str:
    data = _read_bytes(path)
    if _is_binary(data):
        raise ValueError(f"Файл '{_rel(path)}' бинарный и не может быть прочитан.")
    return data.decode("utf-8", errors="replace")


def _make_diff(rel_path: str, old: str, new: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... (вывод обрезан)"


@mcp.tool()
def list_files(path: str = "", pattern: str = "") -> str:
    """Возвращает список файлов проекта с учётом .gitignore.

    Args:
        path: Подпапка относительно корня проекта (по умолчанию — корень).
        pattern: Маска имени файла, например '*.py' (необязательно).
    """
    try:
        base = _resolve(path or ".")
        if not base.is_dir():
            return f"Ошибка: '{path}' не является каталогом."
    except ValueError as exc:
        return f"Ошибка: {exc}"

    files: list[str] = []
    patterns = _gitignore_for(_root())
    for entry in _walk_files(base, patterns):
        rel = _rel(entry)
        if pattern and not fnmatch.fnmatch(entry.name, pattern):
            continue
        files.append(rel)
        if len(files) >= MAX_LIST_RESULTS:
            break

    if not files:
        return "Файлы не найдены."
    header = f"Найдено файлов: {len(files)}"
    if len(files) >= MAX_LIST_RESULTS:
        header += f" (показаны первые {MAX_LIST_RESULTS})"
    return _truncate(header + "\n" + "\n".join(files))


@mcp.tool()
def read_file(path: str) -> str:
    """Читает текстовый файл проекта.

    Args:
        path: Путь к файлу относительно корня проекта. Файлы .env и бинарные
            файлы читать нельзя.
    """
    try:
        target = _resolve(path)
    except ValueError as exc:
        return f"Ошибка: {exc}"
    if not target.is_file():
        return f"Ошибка: '{path}' не является файлом."
    try:
        content = _read_text(target)
    except ValueError as exc:
        return f"Ошибка: {exc}"

    return _truncate(f"--- {_rel(target)} ---\n{content}")


@mcp.tool()
def search_in_files(query: str, path: str = "", mask: str = "") -> str:
    """Ищет подстроку в текстовых файлах проекта (регистронезависимо).

    Args:
        query: Искомый текст.
        path: Подпапка или файл для поиска (по умолчанию — весь проект).
        mask: Маска имени файла, например '*.py' (необязательно).
    """
    if not query:
        return "Ошибка: пустой поисковый запрос."

    try:
        base = _resolve(path or ".")
    except ValueError as exc:
        return f"Ошибка: {exc}"

    needle = query.lower()
    matches: list[str] = []
    patterns = _gitignore_for(_root())
    candidates = [base] if base.is_file() else list(_walk_files(base, patterns))
    for entry in candidates:
        if _is_forbidden(entry):
            continue
        if mask and not fnmatch.fnmatch(entry.name, mask):
            continue
        try:
            text = _read_text(entry)
        except (ValueError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if needle in line.lower():
                matches.append(f"{_rel(entry)}:{line_number}: {line.strip()}")
                if len(matches) >= MAX_SEARCH_MATCHES:
                    break
        if len(matches) >= MAX_SEARCH_MATCHES:
            break

    if not matches:
        return f"Совпадений для '{query}' не найдено."
    header = f"Найдено совпадений: {len(matches)}"
    if len(matches) >= MAX_SEARCH_MATCHES:
        header += f" (показаны первые {MAX_SEARCH_MATCHES})"
    return _truncate(header + "\n" + "\n".join(matches))


@mcp.tool()
def write_file(path: str, content: str, apply: bool = False) -> str:
    """Создаёт или перезаписывает файл проекта (двухшаговое подтверждение).

    При apply=False (по умолчанию) файл НЕ меняется — возвращается preview-diff.
    Покажите diff пользователю; чтобы применить изменение, вызовите инструмент
    повторно с apply=True.

    Args:
        path: Путь к файлу относительно корня проекта.
        content: Новое содержимое файла.
        apply: False — только показать diff; True — записать файл.
    """
    if len(content.encode("utf-8")) > _max_bytes():
        return f"Ошибка: содержимое превышает лимит {_max_bytes()} байт."
    try:
        target = _resolve(path, allow_missing=True)
    except ValueError as exc:
        return f"Ошибка: {exc}"
    if _is_forbidden(target):
        return f"Ошибка: запись в '{target.name}' запрещена."

    rel = _rel(target)
    old = ""
    if target.exists():
        if target.is_dir():
            return f"Ошибка: '{rel}' — это каталог."
        try:
            old = _read_text(target)
        except ValueError as exc:
            return f"Ошибка: {exc}"

    diff = _make_diff(rel, old, content)
    if not diff:
        return f"Файл '{rel}' уже содержит такое содержимое. Изменений нет."
    diff = _truncate(diff)

    if not apply:
        return (
            f"PREVIEW (dry-run) для '{rel}'. Файл не изменён.\n"
            "Чтобы применить, вызовите write_file с apply=True.\n\n"
            f"{diff}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Файл '{rel}' записан.\n\n{diff}"


@mcp.tool()
def replace_in_file(path: str, old: str, new: str, apply: bool = False) -> str:
    """Заменяет подстроку в файле (двухшаговое подтверждение).

    При apply=False (по умолчанию) файл НЕ меняется — возвращается preview-diff.
    Покажите diff пользователю; чтобы применить изменение, вызовите инструмент
    повторно с apply=True.

    Args:
        path: Путь к файлу относительно корня проекта.
        old: Заменяемый фрагмент (должен присутствовать в файле).
        new: Новая подстрока.
        apply: False — только показать diff; True — записать файл.
    """
    try:
        target = _resolve(path)
    except ValueError as exc:
        return f"Ошибка: {exc}"
    if not target.is_file():
        return f"Ошибка: '{path}' не является файлом."
    if not old:
        return "Ошибка: фрагмент для замены не может быть пустым."

    try:
        content = _read_text(target)
    except ValueError as exc:
        return f"Ошибка: {exc}"

    if old not in content:
        return f"Ошибка: фрагмент не найден в '{_rel(target)}'."

    updated = content.replace(old, new)
    rel = _rel(target)
    diff = _truncate(_make_diff(rel, content, updated))

    if not apply:
        return (
            f"PREVIEW (dry-run) для '{rel}'. Файл не изменён.\n"
            "Чтобы применить, вызовите replace_in_file с apply=True.\n\n"
            f"{diff}"
        )

    target.write_text(updated, encoding="utf-8")
    return f"Файл '{rel}' обновлён.\n\n{diff}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
