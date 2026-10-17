from __future__ import annotations

from core.application.protocols.api_key_repository import (
    ApiKeyRepository as DatabaseApiKeyRepository,
)
from core.application.use_cases._helpers.api_key_utils import (
    _hash_api_key,
)


class VerifyApiKeyUseCase:
    """Use case проверки API-ключа при обращении к REST API."""

    def __init__(self, api_key_repository: DatabaseApiKeyRepository):
        self._api_key_repository = api_key_repository

    def execute(self, api_key: str) -> bool:
        if not api_key:
            return False
        record = self._api_key_repository.find_by_hash(_hash_api_key(api_key))
        if record is None:
            return False
        self._api_key_repository.touch(record.id)
        return True
