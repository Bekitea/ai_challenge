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
