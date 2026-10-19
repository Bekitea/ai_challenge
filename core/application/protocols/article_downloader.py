from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ArticleDownloader(Protocol):
    """Загрузка файла статьи (OA-PDF) по URL."""

    def download(self, url: str, destination: Path) -> Path: ...


class ArticleTextExtractor(Protocol):
    """Извлечение текста из скачанного файла статьи (PDF)."""

    def extract(self, path: Path) -> str: ...


class PdfLocator(Protocol):
    """Поиск прямой ссылки на OA-PDF по DOI (например, Unpaywall)."""

    def find_pdf_url(self, doi: str | None) -> str | None: ...
