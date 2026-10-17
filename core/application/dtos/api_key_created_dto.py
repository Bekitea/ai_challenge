from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ApiKeyCreatedDTO:
    """Результат создания API-ключа.

    ``api_key`` содержит исходный секрет и возвращается вызывающему коду
    ровно один раз — при создании; сохранить его нужно сразу.
    """

    id: int
    name: str
    api_key: str
    created_at: datetime
