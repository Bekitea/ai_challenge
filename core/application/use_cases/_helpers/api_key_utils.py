from __future__ import annotations

import hashlib

API_KEY_PREFIX = "aic_"


def _hash_api_key(api_key: str) -> str:
    """Возвращает SHA-256-хеш секрета API-ключа в hex-виде."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
