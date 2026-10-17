from __future__ import annotations

from core.application.dtos.api_key_dto import ApiKeyDTO
from core.application.protocols.api_key_repository import (
    ApiKeyRepository as DatabaseApiKeyRepository,
)


class ListApiKeysUseCase:
    """Use case получения списка API-ключей (без секретов)."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self) -> list[ApiKeyDTO]:
        return [
            ApiKeyDTO(
                id=record.id,
                name=record.name,
                prefix=record.prefix,
                created_at=record.created_at,
                last_used_at=record.last_used_at,
            )
            for record in self._api_key_repository.list_all()
        ]
