from __future__ import annotations

from config import (
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_FILE_EXTENSIONS,
    RAG_FILE_MAX_BYTES,
    RAG_FOLDER_MAX_FILES,
)
from core.application.dtos.add_documents_result import AddDocumentsResult
from core.application.dtos.chunk_ingest import ChunkIngest
from core.application.dtos.document_dto import DocumentDTO
from core.application.dtos.document_status import DOCUMENT_STATUS_ERROR
from core.application.exceptions.document_indexing_error import DocumentIndexingError
from core.application.exceptions.embedding_dimension_mismatch_error import (
    EmbeddingDimensionMismatchError,
)
from core.application.exceptions.knowledge_base_not_found_error import (
    KnowledgeBaseNotFoundError,
)
from core.application.protocols.document_repository import DocumentRepository
from core.application.protocols.file_extractor import FileExtractor
from core.application.protocols.knowledge_base_repository import (
    KnowledgeBaseRepository,
)
from core.application.services.chunking import chunk_text
from core.application.services.rag_model_service import RagModelService


class AddDocumentToKnowledgeBaseUseCase:
    """Use case добавления документа(ов) в базу знаний с индексацией.

    Источником может быть отдельный файл (.txt/.md/.py) или папка. Каждый файл
    становится отдельным документом. Индексация синхронная: при ошибке
    документ помечается статусом ``error`` и не участвует в поиске.
    """

    def __init__(
        self,
        knowledge_base_repository: KnowledgeBaseRepository,
        document_repository: DocumentRepository,
        rag_model_service: RagModelService,
        file_extractor: FileExtractor,
        chunk_size: int = RAG_CHUNK_SIZE,
        chunk_overlap: int = RAG_CHUNK_OVERLAP,
        file_extensions: set[str] | None = None,
        max_bytes: int = RAG_FILE_MAX_BYTES,
        max_files: int = RAG_FOLDER_MAX_FILES,
    ):
        self._kb_repository = knowledge_base_repository
        self._document_repository = document_repository
        self._model_service = rag_model_service
        self._file_extractor = file_extractor
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._file_extensions = file_extensions or set(RAG_FILE_EXTENSIONS)
        self._max_bytes = max_bytes
        self._max_files = max_files

    def execute(
        self, knowledge_base_id: int, source_path: str
    ) -> AddDocumentsResult:
        kb = self._kb_repository.get(knowledge_base_id)
        if kb is None:
            raise KnowledgeBaseNotFoundError(
                f"База знаний #{knowledge_base_id} не найдена."
            )

        if (
            kb.embedding_model != self._model_service.embedding_model_name
            or kb.embedding_dimension != self._model_service.embedding_dimension
        ):
            raise EmbeddingDimensionMismatchError(
                "Модель эмбеддинга текущего приложения не совпадает с моделью, "
                f"под которую создана база знаний '{kb.name}'."
            )

        extracted_files = self._file_extractor.extract_from_path(
            source_path,
            extensions=self._file_extensions,
            max_bytes=self._max_bytes,
            max_files=self._max_files,
        )

        documents: list[DocumentDTO] = []
        for extracted in extracted_files:
            document_id = self._document_repository.create_pending(
                kb_id=kb.id,
                name=extracted.name,
                source_type="file",
                source_path=extracted.source_path,
                content_hash=extracted.content_hash,
            )
            try:
                text_chunks = chunk_text(
                    extracted.text,
                    chunk_size=self._chunk_size,
                    overlap=self._chunk_overlap,
                )
                if not text_chunks:
                    raise DocumentIndexingError("Документ не содержит текста.")

                embeddings = self._model_service.embed_documents(
                    [chunk.text for chunk in text_chunks]
                )
                ingests = [
                    ChunkIngest(
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        char_start=chunk.char_start,
                        char_end=chunk.char_end,
                        token_count=chunk.token_count,
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(
                        text_chunks, embeddings, strict=True
                    )
                ]
                self._document_repository.store_indexed(
                    kb_id=kb.id,
                    document_id=document_id,
                    chunks=ingests,
                )
            except Exception as exc:  # noqa: BLE001
                self._document_repository.set_status(
                    document_id,
                    DOCUMENT_STATUS_ERROR,
                    error_message=str(exc),
                    chunk_count=0,
                )

            document = self._document_repository.get(document_id)
            if document is not None:
                documents.append(document)

        return AddDocumentsResult(documents=documents)
