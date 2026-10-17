from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RagSourceDTO:
    """Источник RAG, использованный в ответе ассистента (DTO)."""

    document_name: str
    chunk_id: int
    chunk_index: int
    text: str
    relevance: float | None = None
