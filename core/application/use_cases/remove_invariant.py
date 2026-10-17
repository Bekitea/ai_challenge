from __future__ import annotations


class RemoveInvariantUseCase:
    """Use case для удаления инварианта из профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, invariant_id: int) -> bool:
        """
        Удаляет инвариант по ID.

        Args:
            invariant_id: ID инварианта для удаления.

        Returns:
            True, если инвариант был удалён, False если не найден.
        """
        return self.task_profile_repository.remove_invariant(invariant_id)
