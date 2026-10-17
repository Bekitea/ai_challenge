from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LlmModelInfo:
    """Описание модели, доступной у конкретного провайдера.

    ``model_id`` — нативный идентификатор модели у провайдера (то, что
    сохраняется в ``AgentSettings.model_id`` и передаётся в запрос), а
    ``display_name`` — человекочитаемое имя для CLI.
    """

    model_id: str
    display_name: str
