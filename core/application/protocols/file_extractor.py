from __future__ import annotations

from typing import Protocol

from core.application.dtos.extracted_file import ExtractedFile


class FileExtractor(Protocol):
    """Порт извлечения текста из файлов/папок для RAG."""

    def extract_from_path(
        self,
        source_path: str,
        extensions: set[str],
        max_bytes: int,
        max_files: int,
    ) -> list[ExtractedFile]:
        """Извлекает документы из файла или папки."""
        ...
