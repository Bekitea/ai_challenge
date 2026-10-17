from __future__ import annotations

from typing import Protocol

from core.domain.dtos.global_memory import GlobalMemory


class GlobalMemoryRepository(Protocol):
    """Порт хранилища общесистемной памяти о пользователе."""

    def get_memory(self) -> GlobalMemory: ...

    def save_memory(self, memory: GlobalMemory) -> None: ...
