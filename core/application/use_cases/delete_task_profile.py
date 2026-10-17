from __future__ import annotations

from core.application.dtos.delete_profile_result_dto import DeleteProfileResultDTO


class DeleteTaskProfileUseCase:
    """Use case для удаления профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def is_linked(self, profile_id: str) -> bool:
        """Возвращает True, если профиль привязан к агентам."""
        return self.task_profile_repository.is_profile_linked_to_agents(profile_id)

    def execute(self, profile_id: str) -> DeleteProfileResultDTO:
        """
        Удаляет профиль задачи.

        Args:
            profile_id: UUID профиля для удаления.

        Returns:
            DeleteProfileResultDTO: ``deleted`` — удалён ли профиль,
            ``linked`` — был ли отказ из-за привязки к агентам.
        """
        # Проверяем, привязан ли профиль к агентам
        if self.task_profile_repository.is_profile_linked_to_agents(profile_id):
            return DeleteProfileResultDTO(deleted=False, linked=True)

        return DeleteProfileResultDTO(
            deleted=self.task_profile_repository.delete_profile(profile_id)
        )
