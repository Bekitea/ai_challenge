from __future__ import annotations

from typing import Protocol

from core.application.dtos.api_key_record import ApiKeyRecord


class ApiKeyRepository(Protocol):
    """Порт репозитория API-ключей доступа к REST API."""

    def create(self, name: str, key_hash: str, prefix: str) -> ApiKeyRecord: ...

    def list_all(self) -> list[ApiKeyRecord]: ...

    def delete(self, key_id: int) -> ApiKeyRecord | None: ...

    def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None: ...

    def touch(self, key_id: int) -> None: ...
