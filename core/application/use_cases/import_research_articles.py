from __future__ import annotations

import logging

from core.application.dtos.add_documents_result import AddDocumentsResult
from core.application.dtos.document_status import DOCUMENT_STATUS_ERROR
from core.application.dtos.import_articles_result_dto import (
    ImportArticlesResultDTO,
    ImportedArticleResultDTO,
)
from core.application.protocols.article_downloader import (
    ArticleDownloader,
    ArticleTextExtractor,
    PdfLocator,
)
from core.application.protocols.research_article_repository import (
    ResearchArticleRepository,
)
from core.application.protocols.research_source import ResearchSource
from core.application.services.research_text import (
    build_article_text,
    library_dirs,
    safe_slug,
)
from core.application.use_cases.add_document_to_knowledge_base import (
    AddDocumentToKnowledgeBaseUseCase,
)
from core.application.use_cases.delete_document import DeleteDocumentUseCase
from core.application.use_cases.ensure_research_library import (
    EnsureResearchLibraryUseCase,
)
from core.domain.entities.research_article import ResearchArticle

logger = logging.getLogger("research.import")


class ImportResearchArticlesUseCase:
    """Импортирует статьи в активную библиотеку чата: PDF/аннотация → RAG."""

    def __init__(
        self,
        ensure_library: EnsureResearchLibraryUseCase,
        article_repository: ResearchArticleRepository,
        source: ResearchSource,
        pdf_locator: PdfLocator,
        downloader: ArticleDownloader,
        text_extractor: ArticleTextExtractor,
        add_document: AddDocumentToKnowledgeBaseUseCase,
        delete_document: DeleteDocumentUseCase,
        data_dir: str,
        batch_limit: int,
    ):
        self._ensure_library = ensure_library
        self._articles = article_repository
        self._source = source
        self._pdf_locator = pdf_locator
        self._downloader = downloader
        self._text_extractor = text_extractor
        self._add_document = add_document
        self._delete_document = delete_document
        self._data_dir = data_dir
        self._batch_limit = max(1, batch_limit)

    def execute(
        self,
        agent_id: int,
        identifiers: list[str],
        *,
        force: bool = False,
        library_name: str | None = None,
    ) -> ImportArticlesResultDTO:
        library = self._ensure_library.execute(agent_id, library_name)
        cleaned = [item.strip() for item in identifiers if item and item.strip()]
        if not cleaned:
            raise ValueError("Список идентификаторов пуст.")
        if len(cleaned) > self._batch_limit:
            raise ValueError(
                f"За один вызов можно импортировать не более "
                f"{self._batch_limit} статей; получите списком меньше "
                "идентификаторов."
            )

        results: list[ImportedArticleResultDTO] = []
        for identifier in cleaned:
            results.append(self._import_one(library, identifier, force))
        return ImportArticlesResultDTO(library=library, results=results)

    def _import_one(
        self, library, identifier: str, force: bool
    ) -> ImportedArticleResultDTO:
        try:
            return self._do_import(library, identifier, force)
        except Exception as exc:  # noqa: BLE001 - ошибка одной статьи не валит пакет
            logger.warning("Импорт статьи %s не удался: %s", identifier, exc)
            return ImportedArticleResultDTO(
                identifier=identifier,
                ok=False,
                status="error",
                detail=str(exc),
            )

    def _do_import(
        self, library, identifier: str, force: bool
    ) -> ImportedArticleResultDTO:
        candidate = self._source.get_by_identifier(identifier)
        if candidate is None:
            return ImportedArticleResultDTO(
                identifier=identifier,
                ok=False,
                status="error",
                detail=(
                    "Статья не найдена в OpenAlex. Проверьте DOI или "
                    "OpenAlex ID."
                ),
            )

        existing = self._articles.get_by_identifier(library.id, identifier)
        if (
            existing is not None
            and existing.status == "indexed"
            and not force
        ):
            return ImportedArticleResultDTO(
                identifier=identifier,
                ok=True,
                status=existing.status,
                article_id=existing.id,
                document_id=existing.document_id,
                title=existing.title,
                detail="Статья уже в библиотеке с полным текстом.",
            )

        article = self._articles.upsert(library.id, candidate, "candidate")
        if existing is not None and existing.document_id is not None:
            self._delete_document.execute(existing.document_id)

        pdf_url = candidate.pdf_url or self._pdf_locator.find_pdf_url(candidate.doi)
        full_text = self._try_full_text(library.id, article, pdf_url)

        has_abstract = bool((candidate.abstract or "").strip())
        if full_text:
            status = "indexed"
            detail = "Проиндексирован полный текст."
        elif has_abstract:
            status = "abstract_only"
            detail = "Полный текст недоступен, проиндексирована аннотация."
        else:
            article = self._articles.set_status(
                article.id,
                "error",
                error_message="Нет ни полного текста, ни аннотации.",
            )
            return ImportedArticleResultDTO(
                identifier=identifier,
                ok=False,
                status="error",
                article_id=article.id if article else None,
                title=candidate.title,
                detail="Нет ни полного текста, ни аннотации.",
            )

        text = build_article_text(
            title=candidate.title,
            authors=candidate.authors,
            year=candidate.publication_year,
            doi=candidate.doi,
            venue=candidate.venue,
            is_open_access=candidate.is_open_access,
            abstract=candidate.abstract,
            full_text=full_text,
        )
        document_id, error = self._index_text(library, article, text)
        if error is not None:
            self._articles.set_status(
                article.id, "error", error_message=error
            )
            return ImportedArticleResultDTO(
                identifier=identifier,
                ok=False,
                status="error",
                article_id=article.id,
                title=candidate.title,
                detail=error,
            )

        self._articles.set_status(article.id, status, document_id=document_id)
        return ImportedArticleResultDTO(
            identifier=identifier,
            ok=True,
            status=status,
            article_id=article.id,
            document_id=document_id,
            title=candidate.title,
            detail=detail,
        )

    def _try_full_text(
        self, library_id: int, article: ResearchArticle, pdf_url: str | None
    ) -> str | None:
        if not pdf_url:
            return None
        pdf_dir, _text_dir = library_dirs(self._data_dir, library_id)
        slug = safe_slug(article.doi or article.openalex_id, f"article_{article.id}")
        pdf_path = pdf_dir / f"{slug}.pdf"
        try:
            self._downloader.download(pdf_url, pdf_path)
            return self._text_extractor.extract(pdf_path)
        except Exception as exc:  # noqa: BLE001 - переходим к аннотации
            logger.warning(
                "Не удалось получить полный текст статьи #%s: %s",
                article.id,
                exc,
            )
            return None

    def _index_text(
        self, library, article: ResearchArticle, text: str
    ) -> tuple[int | None, str | None]:
        if library.knowledge_base_id is None:
            return None, "У научной библиотеки нет базы знаний."
        _pdf_dir, text_dir = library_dirs(self._data_dir, library.id)
        slug = safe_slug(article.doi or article.openalex_id, f"article_{article.id}")
        text_path = text_dir / f"{slug}.txt"
        text_path.write_text(text, encoding="utf-8")

        try:
            result: AddDocumentsResult = self._add_document.execute(
                library.knowledge_base_id, str(text_path)
            )
        except Exception as exc:  # noqa: BLE001
            return None, f"Ошибка индексации: {exc}"

        if not result.documents:
            return None, "Документ не был создан при индексации."
        document = result.documents[0]
        if document.status == DOCUMENT_STATUS_ERROR:
            return document.id, document.error_message or "Ошибка индексации."
        return document.id, None
