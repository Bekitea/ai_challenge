from __future__ import annotations

from core.application.dtos.delete_api_key_result_dto import DeleteApiKeyResultDTO
from core.application.protocols.api_key_repository import (
    ApiKeyRepository as DatabaseApiKeyRepository,
)


class DeleteApiKeyUseCase:
    """Use case отзыва API-ключа по идентификатору."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, key_id: int) -> DeleteApiKeyResultDTO:
        record = self._api_key_repository.delete(key_id)
        if record is None:
            raise ValueError(f"API-ключ #{key_id} не найден.")
        return DeleteApiKeyResultDTO(deleted=True, name=record.name)
