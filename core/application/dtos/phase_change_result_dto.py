from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhaseChangeResultDTO:
    """Результат команды перехода по фазам."""

    success: bool
    message: str
    current_phase: str
