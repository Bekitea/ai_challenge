from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenCounters:
    """Счетчики токенов для чата."""

    chat_prompt_tokens: int = 0
    chat_completion_tokens: int = 0
    tech_prompt_tokens: int = 0
    tech_completion_tokens: int = 0

    @property
    def total_prompt_tokens(self) -> int:
        """Общее количество prompt_tokens."""
        return self.chat_prompt_tokens + self.tech_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Общее количество completion_tokens."""
        return self.chat_completion_tokens + self.tech_completion_tokens
