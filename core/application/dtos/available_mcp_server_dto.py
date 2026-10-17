from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AvailableMcpServerDTO:
    """MCP-сервер из реестра, доступный для подключения (DTO)."""

    name: str
    title: str
    description: str
