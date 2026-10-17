from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AvailableModel:
    """Доступная для выбора модель с указанием провайдера.

    Одна и та же модель может предоставляться разными провайдерами, поэтому
    в списке для UI она представлена отдельной записью на каждого провайдера.
    """

    provider: str
    model_id: str
    display_name: str
