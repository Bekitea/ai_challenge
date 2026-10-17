from __future__ import annotations

from dataclasses import dataclass

from core.application.dtos.document_dto import DocumentDTO
from core.application.dtos.document_status import (
    DOCUMENT_STATUS_ERROR,
)


@dataclass
class AddDocumentsResult:
    """Итог добавления документов в базу знаний."""

    documents: list[DocumentDTO]

    @property
    def ready_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status != DOCUMENT_STATUS_ERROR)

    @property
    def error_count(self) -> int:
        return sum(1 for doc in self.documents if doc.status == DOCUMENT_STATUS_ERROR)
