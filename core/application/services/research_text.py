"""Подготовка текста и путей для индексации научных статей."""

from __future__ import annotations

import re
from pathlib import Path

_SAFE_RE = re.compile(r"[^0-9A-Za-z._-]+")


def safe_slug(value: str | None, fallback: str = "article") -> str:
    """Преобразует идентификатор в безопасное имя файла."""
    text = (value or "").strip()
    text = text.replace("/", "_").replace("\\", "_")
    cleaned = _SAFE_RE.sub("_", text).strip("_.")
    return cleaned[:120] or fallback


def library_dirs(data_dir: str, library_id: int) -> tuple[Path, Path]:
    """Возвращает (папка для PDF, папка для текстов) библиотеки."""
    base = Path(data_dir) / f"library_{library_id}"
    pdf_dir = base / "pdf"
    text_dir = base / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir, text_dir


def build_article_text(
    *,
    title: str,
    authors: list[str] | None,
    year: int | None,
    doi: str | None,
    venue: str | None,
    is_open_access: bool,
    abstract: str | None,
    full_text: str | None,
) -> str:
    """Собирает текст для RAG: шапка с метаданными + аннотация + полный текст."""
    header_lines = [f"# {title}"]
    if authors:
        header_lines.append("Авторы: " + ", ".join(authors))
    if year is not None:
        header_lines.append(f"Год: {year}")
    if doi:
        header_lines.append(f"DOI: {doi}")
    if venue:
        header_lines.append(f"Журнал: {venue}")
    header_lines.append("Открытый доступ: " + ("да" if is_open_access else "нет"))

    body_parts = ["\n".join(header_lines)]
    if abstract:
        body_parts.append("Аннотация:\n" + abstract.strip())
    if full_text:
        body_parts.append("Полный текст:\n" + full_text.strip())
    return "\n\n".join(body_parts).strip()
