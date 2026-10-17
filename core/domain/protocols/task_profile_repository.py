from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.domain.dtos.task_profile import TaskProfile


@dataclass
class InvariantRecord:
    """Запись об инварианте профиля задачи."""

    id: int
    text: str
    created_at: object


class TaskProfileRepository(Protocol):
    """Порт хранилища профилей задач."""

    def get_all_profiles(self) -> list[TaskProfile]: ...

    def get_profile_by_id(self, profile_id: str) -> TaskProfile | None: ...

    def create_profile(
        self,
        name: str,
        description: str,
        preferences: str = "",
        invariants: list[str] | None = None,
    ) -> TaskProfile: ...

    def delete_profile(self, profile_id: str) -> bool: ...

    def is_profile_linked_to_agents(self, profile_id: str) -> bool: ...

    def add_invariant(self, profile_id: str, text: str) -> int: ...

    def remove_invariant(self, invariant_id: int) -> bool: ...

    def get_invariants(self, profile_id: str) -> list[dict]: ...

    def save_facts(self, profile_id: str, facts: list[str]) -> None: ...
