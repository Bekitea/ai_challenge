from __future__ import annotations

from core.application.dtos.task_profile_detail_dto import TaskProfileDetailDTO
from core.application.mappers.task_profile_mapper import (
    _task_profile_to_detail,
)


class GetTaskProfileMemoryUseCase:
    """Use case для просмотра памяти выбранного профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str) -> TaskProfileDetailDTO | None:
        """
        Получает информацию о профиле задачи и его память.

        Args:
            profile_id: UUID профиля задачи.

        Returns:
            TaskProfileDetailDTO или None, если профиль не найден.
        """
        profile = self.task_profile_repository.get_profile_by_id(profile_id)
        if profile is None:
            return None
        return _task_profile_to_detail(profile)
