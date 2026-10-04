"""Извлечение текста из файлов .txt/.md/.py для RAG.

Пользователь может передать путь к отдельному файлу или к папке: в этом
случае рекурсивно собираются все поддерживаемые файлы.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from rag_errors import FileExtractionError, UnsupportedFileTypeError

logger = logging.getLogger("rag.file_extractor")

_ENCODINGS = ("utf-8", "utf-8-sig", "cp1251")


@dataclass
class ExtractedFile:
    """Текст, извлечённый из одного файла."""

    name: str
    source_path: str
    text: str
    content_hash: str


def _read_file(path: Path, max_bytes: int) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FileExtractionError(f"Не удалось прочитать файл '{path}': {exc}") from exc

    if size > max_bytes:
        raise FileExtractionError(
            f"Файл '{path.name}' превышает лимит {max_bytes} байт."
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FileExtractionError(f"Не удалось прочитать файл '{path}': {exc}") from exc

    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileExtractionError(
        f"Не удалось определить кодировку файла '{path.name}'."
    )


def _build_extracted(path: Path, text: str) -> ExtractedFile:
    return ExtractedFile(
        name=path.name,
        source_path=str(path),
        text=text,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _try_extract(path: Path, max_bytes: int) -> ExtractedFile | None:
    """Извлекает файл; возвращает None, если файл пуст (такие пропускаются)."""
    text = _read_file(path, max_bytes)
    if not text.strip():
        logger.debug("Пропуск пустого файла: %s", path)
        return None
    return _build_extracted(path, text)


def _iter_source_files(
    directory: Path,
    extensions: set[str],
    max_files: int,
) -> list[Path]:
    files: list[Path] = []
    for candidate in sorted(directory.rglob("*")):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in extensions:
            continue
        files.append(candidate)
        if len(files) >= max_files:
            break
    return files


def extract_from_path(
    source_path: str,
    extensions: set[str],
    max_bytes: int,
    max_files: int,
) -> list[ExtractedFile]:
    """Извлекает документы из файла или папки.

    Пустые файлы пропускаются. При обходе папки файлы, которые не удалось
    прочитать (размер/кодировка), также пропускаются, чтобы один проблемный
    файл не срывал индексацию остальных.

    Raises:
        FileExtractionError: Если путь не существует или папка не содержит
            поддерживаемых файлов.
        UnsupportedFileTypeError: Если расширение одиночного файла не
            поддерживается.
    """
    path = Path(source_path).expanduser()
    if not path.exists():
        raise FileExtractionError(f"Путь '{source_path}' не найден.")

    if path.is_dir():
        files = _iter_source_files(path, extensions, max_files)
        if not files:
            raise FileExtractionError(
                f"В папке '{source_path}' нет поддерживаемых файлов "
                f"({', '.join(sorted(extensions))})."
            )
        extracted: list[ExtractedFile] = []
        for item in files:
            try:
                result = _try_extract(item, max_bytes)
            except FileExtractionError as exc:
                logger.debug("Пропуск файла '%s': %s", item, exc)
                continue
            if result is not None:
                extracted.append(result)
        return extracted

    if path.suffix.lower() not in extensions:
        raise UnsupportedFileTypeError(
            f"Формат '{path.suffix}' не поддерживается. "
            f"Допустимые: {', '.join(sorted(extensions))}."
        )
    single = _try_extract(path, max_bytes)
    return [single] if single is not None else []
