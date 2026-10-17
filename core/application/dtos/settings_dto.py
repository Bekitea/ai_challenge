from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SettingsDTO:
    """DTO настроек чата. Используется и на вход, и на выход."""

    model_id: str | None = None
    provider: str | None = None
    top_k: int | None = None
    top_p: float | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    context_window_size: int | None = None
    reranker_enabled: bool = True
