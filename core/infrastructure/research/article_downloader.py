from __future__ import annotations

import logging
from pathlib import Path

import requests

import config

logger = logging.getLogger("research.downloader")

_PDF_MAGIC = b"%PDF"


class ArticleDownloadError(RuntimeError):
    """Не удалось скачать файл статьи."""


class HttpArticleDownloader:
    """Скачивает OA-файл статьи с ограничением размера и проверкой, что это PDF."""

    def __init__(
        self,
        max_bytes: int | None = None,
        timeout: int = 60,
    ):
        self._max_bytes = max_bytes or config.RESEARCH_MAX_PDF_BYTES
        self._timeout = timeout

    def download(self, url: str, destination: Path) -> Path:
        clean_url = (url or "").strip()
        if not clean_url:
            raise ArticleDownloadError("Пустой URL файла статьи.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "User-Agent": "ai-chat-research/1.0 (dissertation research assistant)",
            "Accept": "application/pdf,*/*",
        }
        try:
            with requests.get(
                clean_url,
                headers=headers,
                timeout=self._timeout,
                stream=True,
                allow_redirects=True,
            ) as response:
                if not response.ok:
                    raise ArticleDownloadError(
                        f"HTTP {response.status_code} при загрузке PDF."
                    )
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise ArticleDownloadError(
                            "Файл статьи превышает допустимый размер "
                            f"({self._max_bytes} байт)."
                        )
                    chunks.append(chunk)
        except requests.RequestException as exc:
            raise ArticleDownloadError(f"Сетевая ошибка загрузки PDF: {exc}") from exc

        raw = b"".join(chunks)
        if not raw.startswith(_PDF_MAGIC):
            raise ArticleDownloadError(
                "Загруженный файл не является PDF (проверьте ссылку)."
            )

        destination.write_bytes(raw)
        return destination
