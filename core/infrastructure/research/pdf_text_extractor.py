from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

import config

logger = logging.getLogger("research.pdf")


class PdfTextExtractionError(RuntimeError):
    """Не удалось извлечь текст из PDF."""


class PdfTextExtractor:
    """Извлекает текст из PDF через pypdf с ограничением числа страниц."""

    def __init__(
        self,
        max_pages: int | None = None,
        max_chars: int | None = None,
    ):
        self._max_pages = max_pages or config.RESEARCH_MAX_PDF_PAGES
        self._max_chars = max_chars or config.RESEARCH_MAX_FULLTEXT_CHARS

    def extract(self, path: Path) -> str:
        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise PdfTextExtractionError(f"Не удалось открыть PDF: {exc}") from exc

        parts: list[str] = []
        length = 0
        for page in reader.pages[: self._max_pages]:
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                logger.debug("Страница PDF пропущена из-за ошибки: %s", exc)
                continue
            if not text.strip():
                continue
            parts.append(text)
            length += len(text)
            if length >= self._max_chars:
                break

        extracted = "\n".join(parts).strip()
        if not extracted:
            raise PdfTextExtractionError(
                "PDF не содержит извлекаемого текста (возможно, это скан)."
            )
        return extracted[: self._max_chars]
