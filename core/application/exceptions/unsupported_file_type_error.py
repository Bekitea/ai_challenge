from __future__ import annotations

from core.application.exceptions.file_extraction_error import FileExtractionError


class UnsupportedFileTypeError(FileExtractionError):
    """Расширение файла не поддерживается."""
