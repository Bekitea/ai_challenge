from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExtractedFile:
    """Текст, извлечённый из одного файла."""

    name: str
    source_path: str
    text: str
    content_hash: str
