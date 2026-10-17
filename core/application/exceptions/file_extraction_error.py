from __future__ import annotations

from core.application.exceptions.rag_error import RagError


class FileExtractionError(RagError):
    """Ошибка чтения/извлечения текста из файла."""
