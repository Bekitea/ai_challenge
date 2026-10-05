"""DTO и доменные структуры RAG-подсистемы.

Эти объекты не зависят от ORM и провайдеров — ими обмениваются слои
приложения и представления.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class KnowledgeBaseDTO:
    """Информация о базе знаний для отображения."""

    id: int
    name: str
    description: str | None
    embedding_model: str
    embedding_dimension: int
    created_at: datetime
    updated_at: datetime | None = None
    document_count: int | None = None
    chunk_count: int | None = None


@dataclass
class DocumentDTO:
    """Информация о документе базы знаний."""

    id: int
    knowledge_base_id: int
    name: str
    source_type: str
    source_path: str | None
    status: str
    error_message: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime | None = None


@dataclass
class ChunkDTO:
    """Информация о чанке документа (без эмбеддинга)."""

    id: int
    document_id: int
    chunk_index: int
    text: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    created_at: datetime


@dataclass
class RagContextChunk:
    """Чанк, попавший в RAG-контекст диалога."""

    chunk_id: int
    document_id: int
    knowledge_base_id: int
    document_name: str
    chunk_index: int
    text: str
    vector_distance: float | None = None
    rerank_score: float | None = None

    @property
    def relevance(self) -> float | None:
        """Релевантность чанка в единой шкале [0..1].

        При реранкинге используется score кросс-энкодера, иначе векторная
        дистанция (косинусная, 0..2) переводится в ``1 - distance / 2``.
        ``None`` означает, что оценка недоступна.
        """
        if self.rerank_score is not None:
            return self.rerank_score
        if self.vector_distance is not None:
            value = 1.0 - self.vector_distance / 2.0
            return max(0.0, min(1.0, value))
        return None


@dataclass
class RagRetrievalResult:
    """Итог RAG-поиска для диалога агента."""

    chunks: list[RagContextChunk]
    has_knowledge_bases: bool
    below_threshold: bool = False


@dataclass
class RetrievedChunk:
    """Чанк, поднятый из БД для RAG-поиска (без оценки релевантности)."""

    chunk_id: int
    document_id: int
    knowledge_base_id: int
    document_name: str
    chunk_index: int
    text: str


# Статусы индексации документа
DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_INDEXING = "indexing"
DOCUMENT_STATUS_READY = "ready"
DOCUMENT_STATUS_ERROR = "error"
