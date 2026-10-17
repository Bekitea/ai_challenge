from __future__ import annotations

from core.application.dtos.invariant_info import InvariantInfo


class ListInvariantsUseCase:
    """Use case для получения списка инвариантов профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> list[InvariantInfo]:
        """
        Возвращает список инвариантов профиля.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            Список InvariantInfo, отсортированный по дате создания.
        """
        invariants = self.task_profile_repository.get_invariants(profile_id)
        return [
            InvariantInfo(
                id=inv["id"],
                text=inv["text"],
                created_at=inv["created_at"],
            )
            for inv in invariants
        ]
