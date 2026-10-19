from __future__ import annotations

from core.application.dtos.research_article_dto import ResearchArticleDTO
from core.application.dtos.research_library_dto import ResearchLibraryDTO
from core.domain.entities.research_article import ResearchArticle
from core.domain.entities.research_library import ResearchLibrary


def research_library_to_dto(library: ResearchLibrary) -> ResearchLibraryDTO:
    """Преобразует сущность библиотеки в DTO."""
    if library.id is None:
        raise ValueError("Библиотека без id не может быть отдана в DTO.")
    return ResearchLibraryDTO(
        id=library.id,
        name=library.name,
        knowledge_base_id=library.knowledge_base_id,
        description=library.description,
        goal=library.goal,
        field=library.field,
        keywords=list(library.keywords),
        year_from=library.year_from,
        year_to=library.year_to,
        language=library.language,
        created_at=library.created_at,
        updated_at=library.updated_at,
    )


def research_article_to_dto(article: ResearchArticle) -> ResearchArticleDTO:
    """Преобразует сущность статьи в DTO."""
    if article.id is None:
        raise ValueError("Статья без id не может быть отдана в DTO.")
    return ResearchArticleDTO(
        id=article.id,
        library_id=article.library_id,
        title=article.title,
        openalex_id=article.openalex_id,
        doi=article.doi,
        authors=list(article.authors),
        publication_year=article.publication_year,
        venue=article.venue,
        language=article.language,
        abstract=article.abstract,
        cited_by_count=article.cited_by_count,
        is_open_access=article.is_open_access,
        pdf_url=article.pdf_url,
        landing_url=article.landing_url,
        source=article.source,
        status=article.status,
        error_message=article.error_message,
        document_id=article.document_id,
        summary=article.summary,
        summary_model=article.summary_model,
        summary_updated_at=article.summary_updated_at,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )
