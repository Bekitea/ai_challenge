from __future__ import annotations

from core.application.dtos.task_profile_info import TaskProfileInfo
from core.application.mappers.task_profile_mapper import (
    _task_profile_to_info,
)


class CreateTaskProfileUseCase:
    """Use case для создания нового профиля задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(
        self,
        name: str,
        description: str,
        preferences: str = "",
        invariants: list[str] | None = None,
    ) -> TaskProfileInfo:
        """
        Создаёт новый профиль задачи.

        Args:
            name: Название профиля.
            description: Описание задачи.
            preferences: Инструкции и предпочтения пользователя (опционально).
            invariants: Список строгих правил/ограничений (опционально).

        Returns:
            TaskProfileInfo: Созданный профиль.
        """
        profile = self.task_profile_repository.create_profile(
            name, description, preferences, invariants
        )
        return _task_profile_to_info(profile)
