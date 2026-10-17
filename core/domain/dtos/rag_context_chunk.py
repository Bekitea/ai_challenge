from __future__ import annotations

from dataclasses import dataclass


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
