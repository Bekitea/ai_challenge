from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeleteProfileResultDTO:
    """Результат удаления профиля задачи."""

    deleted: bool
    linked: bool = False
