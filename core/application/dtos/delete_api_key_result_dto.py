from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteApiKeyResultDTO:
    """Результат удаления API-ключа."""

    deleted: bool
    name: str | None
