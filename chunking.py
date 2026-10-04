"""Разбиение текста документа на чанки.

Чанкинг выполняется по символам с перекрытием. Границы по возможности
смещаются к ближайшему переводу строки/пробелу, чтобы не разрывать слова.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    """Фрагмент текста с позициями в нормализованном тексте."""

    chunk_index: int
    text: str
    char_start: int
    char_end: int

    @property
    def token_count(self) -> int:
        """Приблизительная оценка числа токенов."""
        return max(1, len(self.text) // 4)


def normalize_text(text: str) -> str:
    """Нормализует переводы строк."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[TextChunk]:
    """Разбивает текст на чанки.

    Args:
        text: Исходный текст.
        chunk_size: Целевой размер чанка в символах.
        overlap: Перекрытие между соседними чанками в символах.

    Returns:
        Список непустых чанков в порядке следования.
    """
    normalized = normalize_text(text)
    total = len(normalized)
    if total == 0:
        return []

    chunk_size = max(1, chunk_size)
    overlap = max(0, min(overlap, chunk_size - 1))
    step = max(1, chunk_size - overlap)

    chunks: list[TextChunk] = []
    position = 0
    index = 0

    while position < total:
        end = min(position + chunk_size, total)
        if end < total:
            boundary = normalized.rfind("\n", position + step, end)
            if boundary == -1:
                boundary = normalized.rfind(" ", position + step, end)
            if boundary != -1:
                end = boundary + 1

        piece = normalized[position:end]
        stripped = piece.strip()
        if stripped:
            lead = len(piece) - len(piece.lstrip())
            start = position + lead
            chunks.append(
                TextChunk(
                    chunk_index=index,
                    text=stripped,
                    char_start=start,
                    char_end=start + len(stripped),
                )
            )
            index += 1

        if end >= total:
            break
        position = max(end - overlap, position + step)

    return chunks
