from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArticleSummaryResultDTO:
    """Результат суммаризации одной статьи."""

    article_id: int
    title: str
    ok: bool
    summary: str | None = None
    error: str | None = None


@dataclass
class SummarizeArticlesResultDTO:
    """Результат пакетной суммаризации статей библиотеки."""

    results: list[ArticleSummaryResultDTO] = field(default_factory=list)
