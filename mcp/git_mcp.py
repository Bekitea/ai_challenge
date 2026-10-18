#!/usr/bin/env python3
"""MCP-сервер доступа к git-репозиторию проекта (только чтение).

Даёт ассистенту контекст проекта: текущую ветку, статус, список изменённых
файлов и diff. Все команды выполняются в корне репозитория, найденном
относительно этого файла (``<repo>/mcp/git_mcp.py`` -> ``<repo>``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server import MCPServer

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Ограничиваем объём вывода, чтобы не переполнять контекст LLM.
MAX_OUTPUT_CHARS = 20000

mcp = MCPServer(
    "GitRepository",
    description="Доступ к git-репозиторию проекта: ветка, статус, изменения, diff.",
)


def _run_git(args: list[str], timeout: int = 30) -> tuple[str | None, str | None]:
    """Запускает git-команду в корне проекта.

    Возвращает ``(stdout, error)``: при успехе error=None, при ошибке
    stdout=None и текст ошибки.
    """
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return None, "не найден исполняемый файл git"
    except subprocess.TimeoutExpired:
        return None, "превышено время ожидания git"

    if completed.returncode != 0:
        message = (completed.stderr or "").strip()
        return None, message or f"git завершился с кодом {completed.returncode}"

    return completed.stdout or "", None


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... (вывод обрезан)"


@mcp.tool()
def get_current_branch() -> str:
    """Возвращает имя текущей git-ветки проекта."""
    output, error = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if error is not None:
        return f"Ошибка: {error}"
    branch = output.strip() or "(пусто)"
    return f"Текущая ветка: {branch}"


@mcp.tool()
def get_status() -> str:
    """Возвращает краткий git-статус рабочей копии (ветка + изменённые файлы)."""
    output, error = _run_git(["status", "--short", "--branch"])
    if error is not None:
        return f"Ошибка: {error}"
    return _truncate(output.strip() or "Рабочая копия чистая.")


@mcp.tool()
def list_changed_files(base: str = "") -> str:
    """Показывает список изменённых файлов.

    Args:
        base: Базовая ветка/коммит для сравнения (например, 'main'). Если не
            указан, возвращаются изменения рабочей копии относительно HEAD.
    """
    if base:
        output, error = _run_git(["diff", "--name-only", f"{base}...HEAD"])
    else:
        output, error = _run_git(["diff", "--name-only", "HEAD"])
    if error is not None:
        return f"Ошибка: {error}"

    files = [line.strip() for line in output.splitlines() if line.strip()]
    if not files:
        return "Изменённых файлов нет."
    return _truncate("Изменённые файлы:\n" + "\n".join(f"- {name}" for name in files))


@mcp.tool()
def get_diff(base: str = "", path: str = "") -> str:
    """Возвращает unified diff изменений.

    Args:
        base: Базовая ветка/коммит для сравнения (например, 'main'). Если не
            указан, показываются изменения рабочей копии относительно HEAD.
        path: Ограничить diff одним файлом или подпапкой (необязательно).
    """
    args = ["diff"]
    if base:
        args.append(base)
    else:
        args.append("HEAD")
    if path:
        args.extend(["--", path])

    output, error = _run_git(args)
    if error is not None:
        return f"Ошибка: {error}"
    diff = output.strip()
    if not diff:
        return "Изменений нет."
    return _truncate(diff)


if __name__ == "__main__":
    mcp.run(transport="stdio")
