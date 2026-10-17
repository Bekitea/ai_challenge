"""Эндпоинты баз знаний, документов, чанков и поиска (RAG)."""

from __future__ import annotations

import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from core.presentation.api.deps import UseCasesDep
from core.presentation.api.schemas import (
    ActionResult,
    Chunk,
    CreateKnowledgeBaseRequest,
    Document,
    DocumentUploadResult,
    KnowledgeBase,
    RagContextChunk,
    SearchRequest,
)

router = APIRouter(tags=["knowledge-bases"])


@router.get("/knowledge-bases", response_model=list[KnowledgeBase])
def list_knowledge_bases(uc: UseCasesDep):
    """Список баз знаний."""
    return uc.list_knowledge_bases.execute()


@router.post(
    "/knowledge-bases", response_model=KnowledgeBase, status_code=status.HTTP_201_CREATED
)
def create_knowledge_base(
    request: CreateKnowledgeBaseRequest, uc: UseCasesDep
):
    """Создаёт базу знаний."""
    return uc.create_knowledge_base.execute(request.name, request.description)


@router.delete("/knowledge-bases/{kb_id}", response_model=ActionResult)
def delete_knowledge_base(kb_id: int, uc: UseCasesDep):
    """Удаляет базу знаний вместе с документами и векторами."""
    deleted = uc.delete_knowledge_base.execute(kb_id)
    return ActionResult(success=deleted)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[Document])
def list_documents(kb_id: int, uc: UseCasesDep):
    """Документы базы знаний."""
    return uc.list_documents.execute(kb_id)


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentUploadResult,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    kb_id: int,
    uc: UseCasesDep,
    file: Annotated[UploadFile, File()],
):
    """Загружает и индексирует документ (.txt/.md/.py) в базе знаний.

    Файл сохраняется во временную папку, после чего вызывается обычный
    ``add_document`` use case по пути. Логика извлечения/чанкинга не
    дублируется — она полностью в бизнес-слое.
    """
    filename = os.path.basename(file.filename or "upload.txt")
    tmp_dir = tempfile.mkdtemp(prefix="kb_upload_")
    tmp_path = os.path.join(tmp_dir, filename)
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(file.file.read())
        result = uc.add_document.execute(kb_id, tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

    return DocumentUploadResult(
        documents=result.documents,
        ready_count=result.ready_count,
        error_count=result.error_count,
    )


@router.delete("/documents/{document_id}", response_model=ActionResult)
def delete_document(document_id: int, uc: UseCasesDep):
    """Удаляет документ вместе с чанками и векторами."""
    deleted = uc.delete_document.execute(document_id)
    return ActionResult(success=deleted)


@router.get("/documents/{document_id}/chunks", response_model=list[Chunk])
def list_document_chunks(document_id: int, uc: UseCasesDep):
    """Чанки документа."""
    return uc.list_document_chunks.execute(document_id)


@router.post(
    "/knowledge-bases/{kb_id}/search", response_model=list[RagContextChunk]
)
def search_knowledge_base(
    kb_id: int, request: SearchRequest, uc: UseCasesDep
):
    """Поиск по одной базе знаний."""
    return uc.search_knowledge_base.execute(kb_id, request.query, request.top_k)


@router.get(
    "/chats/{chat_id}/knowledge-bases", response_model=list[KnowledgeBase]
)
def list_agent_knowledge_bases(
    chat_id: int, uc: UseCasesDep
):
    """Базы знаний, подключённые к чату."""
    return uc.list_agent_knowledge_bases.execute(chat_id)


@router.post(
    "/chats/{chat_id}/knowledge-bases/{kb_id}", response_model=ActionResult
)
def attach_knowledge_base(
    chat_id: int, kb_id: int, uc: UseCasesDep
):
    """Подключает базу знаний к чату."""
    success, message = uc.attach_knowledge_base.execute(chat_id, kb_id)
    return ActionResult(success=success, message=message)


@router.delete(
    "/chats/{chat_id}/knowledge-bases/{kb_id}", response_model=ActionResult
)
def detach_knowledge_base(
    chat_id: int, kb_id: int, uc: UseCasesDep
):
    """Отключает базу знаний от чата."""
    success, message = uc.detach_knowledge_base.execute(chat_id, kb_id)
    return ActionResult(success=success, message=message)
