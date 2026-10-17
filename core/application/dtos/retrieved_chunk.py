from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """Чанк, поднятый из БД для RAG-поиска (без оценки релевантности)."""

    chunk_id: int
    document_id: int
    knowledge_base_id: int
    document_name: str
    chunk_index: int
    text: str
