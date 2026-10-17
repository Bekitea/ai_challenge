from __future__ import annotations

from core.application.dtos.invariant_info import InvariantInfo


class AddInvariantUseCase:
    """Use case для добавления инварианта в профиль задачи."""

    def __init__(self, task_profile_repository):
        self.task_profile_repository = task_profile_repository

    def execute(self, profile_id: str, text: str) -> InvariantInfo:
        """
        Добавляет инвариант в профиль задачи.

        Args:
            profile_id: UUID профиля задачи.
            text: Текст инварианта (строгое правило/ограничение).

        Returns:
            InvariantInfo: Информация о созданном инварианте.

        Raises:
            ValueError: Если текст пустой или профиль не найден.
        """
        stripped = text.strip()
        if not stripped:
            raise ValueError("Текст инварианта не может быть пустым")
        invariant_id = self.task_profile_repository.add_invariant(profile_id, stripped)
        # Загружаем созданный инвариант для возврата полной информации
        invariants = self.task_profile_repository.get_invariants(profile_id)
        for inv in invariants:
            if inv["id"] == invariant_id:
                return InvariantInfo(
                    id=inv["id"],
                    text=inv["text"],
                    created_at=inv["created_at"],
                )
        raise RuntimeError("Инвариант не найден после создания")
