from __future__ import annotations

from dataclasses import dataclass, field

from core.application.dtos.rag_source_dto import RagSourceDTO


@dataclass
class CodeReviewRequestDTO:
    """Данные PR, собранные раннером CI и переданные бэкенду на ревью (DTO).

    Раннер вычисляет diff и метаданные локально и отправляет их одним HTTP
    POST-запросом; бэкенд не имеет доступа к git-репозиторию.
    """

    repo: str = ""
    pr_number: int | None = None
    pr_title: str = ""
    author: str = ""
    base_branch: str = ""
    head_branch: str = ""
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""


@dataclass
class CodeReviewResultDTO:
    """Результат AI-ревью PR (DTO)."""

    review: str
    rag_sources: list[RagSourceDTO] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str | None = None
