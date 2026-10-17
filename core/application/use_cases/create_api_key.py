from __future__ import annotations

import secrets

from core.application.dtos.api_key_created_dto import ApiKeyCreatedDTO
from core.application.protocols.api_key_repository import (
    ApiKeyRepository as DatabaseApiKeyRepository,
)
from core.application.use_cases._helpers.api_key_utils import (
    API_KEY_PREFIX,
    _hash_api_key,
)


class CreateApiKeyUseCase:
    """Use case создания нового API-ключа."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, name: str) -> ApiKeyCreatedDTO:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Название API-ключа не может быть пустым.")

        api_key = API_KEY_PREFIX + secrets.token_urlsafe(32)
        record = self._api_key_repository.create(
            name=clean_name,
            key_hash=_hash_api_key(api_key),
            prefix=api_key[: len(API_KEY_PREFIX) + 8],
        )
        return ApiKeyCreatedDTO(
            id=record.id,
            name=record.name,
            api_key=api_key,
            created_at=record.created_at,
        )
