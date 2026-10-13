"""Аутентификация REST API по API-ключу.

Ключ передаётся в заголовке ``Authorization: Bearer <key>``. Проверка
выполняется отдельным use case'ом (``verify_api_key``), который сравнивает
SHA-256-хеш ключа с сохранёнными метаданными. Секреты в открытом виде в БД
не хранятся.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.deps import UseCasesDep

_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
    uc: UseCasesDep,
) -> None:
    """Зависимость FastAPI: пропускает запрос только с валидным API-ключом."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется действующий API-ключ (Authorization: Bearer <key>).",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    if not uc.verify_api_key.execute(credentials.credentials):
        raise unauthorized
