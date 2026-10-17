from __future__ import annotations

from core.application.dtos.task_profile_info import TaskProfileInfo
from core.application.mappers.task_profile_mapper import (
    _task_profile_to_info,
)


class ListTaskProfilesUseCase:
    """Use case для просмотра списка профилей задач."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self) -> list[TaskProfileInfo]:
        """
        Получает список всех профилей задач.

        Returns:
            Список TaskProfileInfo.
        """
        profiles = self.task_profile_repository.get_all_profiles()
        return [_task_profile_to_info(p) for p in profiles]
