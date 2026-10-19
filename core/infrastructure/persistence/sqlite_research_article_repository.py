from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.services.research_identifiers import (
    normalize_doi,
    normalize_openalex_id,
)
from core.domain.entities.research_article import ResearchArticle
from core.infrastructure.persistence.orm import ResearchArticleORM


def _now() -> datetime:
    return datetime.now().astimezone()


def _load_authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if str(item).strip()]


def _dump_authors(authors: list[str]) -> str:
    return json.dumps(authors, ensure_ascii=False)


class SqliteResearchArticleRepository:
    """Репозиторий статей научной библиотеки."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _to_entity(orm: ResearchArticleORM) -> ResearchArticle:
        return ResearchArticle(
            id=orm.id,
            library_id=orm.library_id,
            title=orm.title,
            openalex_id=orm.openalex_id,
            doi=orm.doi,
            authors=_load_authors(orm.authors_json),
            publication_year=orm.publication_year,
            venue=orm.venue,
            language=orm.language,
            abstract=orm.abstract,
            cited_by_count=orm.cited_by_count,
            is_open_access=bool(orm.is_open_access),
            pdf_url=orm.pdf_url,
            landing_url=orm.landing_url,
            source=orm.source,
            status=orm.status,
            error_message=orm.error_message,
            document_id=orm.document_id,
            summary=orm.summary,
            summary_model=orm.summary_model,
            summary_updated_at=orm.summary_updated_at,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _find_orm(
        session: Session, library_id: int, doi: str | None, openalex_id: str | None
    ) -> ResearchArticleORM | None:
        conditions = []
        if doi:
            conditions.append(
                func.lower(ResearchArticleORM.doi) == doi.lower()
            )
        if openalex_id:
            conditions.append(
                func.upper(ResearchArticleORM.openalex_id) == openalex_id.upper()
            )
        if not conditions:
            return None
        return session.scalar(
            select(ResearchArticleORM).where(
                ResearchArticleORM.library_id == library_id,
                or_(*conditions),
            )
        )

    def upsert(
        self,
        library_id: int,
        candidate: ArticleCandidateDTO,
        status: str,
    ) -> ResearchArticle:
        doi = normalize_doi(candidate.doi)
        openalex_id = normalize_openalex_id(candidate.openalex_id)
        with self._session_factory() as session:
            orm = self._find_orm(session, library_id, doi, openalex_id)
            if orm is None:
                orm = ResearchArticleORM(
                    library_id=library_id,
                    title=candidate.title or "Без названия",
                    doi=doi,
                    openalex_id=openalex_id,
                    status=status,
                )
                session.add(orm)

            if candidate.title:
                orm.title = candidate.title
            if doi:
                orm.doi = doi
            if openalex_id:
                orm.openalex_id = openalex_id
            if candidate.authors is not None:
                orm.authors_json = _dump_authors(candidate.authors)
            if candidate.publication_year is not None:
                orm.publication_year = candidate.publication_year
            if candidate.venue is not None:
                orm.venue = candidate.venue
            if candidate.language is not None:
                orm.language = candidate.language
            if candidate.abstract is not None:
                orm.abstract = candidate.abstract
            if candidate.cited_by_count is not None:
                orm.cited_by_count = candidate.cited_by_count
            orm.is_open_access = bool(candidate.is_open_access)
            if candidate.pdf_url is not None:
                orm.pdf_url = candidate.pdf_url
            if candidate.landing_url is not None:
                orm.landing_url = candidate.landing_url
            if candidate.source is not None:
                orm.source = candidate.source
            orm.status = status
            if status != "error":
                orm.error_message = None
            orm.updated_at = _now()
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def get(self, article_id: int) -> ResearchArticle | None:
        with self._session_factory() as session:
            orm = session.get(ResearchArticleORM, article_id)
            return self._to_entity(orm) if orm is not None else None

    def get_by_identifier(
        self, library_id: int, identifier: str
    ) -> ResearchArticle | None:
        doi = normalize_doi(identifier)
        openalex_id = normalize_openalex_id(identifier)
        with self._session_factory() as session:
            orm = self._find_orm(session, library_id, doi, openalex_id)
            return self._to_entity(orm) if orm is not None else None

    def get_by_document(
        self, library_id: int, document_id: int
    ) -> ResearchArticle | None:
        with self._session_factory() as session:
            orm = session.scalar(
                select(ResearchArticleORM).where(
                    ResearchArticleORM.library_id == library_id,
                    ResearchArticleORM.document_id == document_id,
                )
            )
            return self._to_entity(orm) if orm is not None else None

    @staticmethod
    def _conditions(
        library_id: int,
        query: str | None,
        year_from: int | None,
        year_to: int | None,
        status: str | None,
    ) -> list:
        conditions: list = [ResearchArticleORM.library_id == library_id]
        clean_query = (query or "").strip().lower()
        if clean_query:
            pattern = f"%{clean_query}%"
            conditions.append(
                or_(
                    func.lower(ResearchArticleORM.title).like(pattern),
                    func.lower(
                        func.coalesce(ResearchArticleORM.abstract, "")
                    ).like(pattern),
                    func.lower(
                        func.coalesce(ResearchArticleORM.authors_json, "")
                    ).like(pattern),
                )
            )
        if year_from is not None:
            conditions.append(ResearchArticleORM.publication_year >= year_from)
        if year_to is not None:
            conditions.append(ResearchArticleORM.publication_year <= year_to)
        if status:
            conditions.append(ResearchArticleORM.status == status)
        return conditions

    def list(
        self,
        library_id: int,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResearchArticle]:
        with self._session_factory() as session:
            statement = (
                select(ResearchArticleORM)
                .where(
                    *self._conditions(
                        library_id, query, year_from, year_to, status
                    )
                )
                .order_by(
                    ResearchArticleORM.publication_year.desc().nullslast(),
                    ResearchArticleORM.cited_by_count.desc().nullslast(),
                    ResearchArticleORM.id.desc(),
                )
                .limit(max(1, min(limit, 5000)))
                .offset(max(0, offset))
            )
            rows = session.scalars(statement).all()
            return [self._to_entity(row) for row in rows]

    def update(self, article: ResearchArticle) -> ResearchArticle:
        if article.id is None:
            raise ValueError("Нельзя обновить статью без id.")
        with self._session_factory() as session:
            orm = session.get(ResearchArticleORM, article.id)
            if orm is None:
                raise ValueError(f"Статья #{article.id} не найдена.")
            orm.title = article.title
            orm.doi = normalize_doi(article.doi)
            orm.openalex_id = normalize_openalex_id(article.openalex_id)
            orm.authors_json = _dump_authors(article.authors)
            orm.publication_year = article.publication_year
            orm.venue = article.venue
            orm.language = article.language
            orm.abstract = article.abstract
            orm.cited_by_count = article.cited_by_count
            orm.is_open_access = article.is_open_access
            orm.pdf_url = article.pdf_url
            orm.landing_url = article.landing_url
            orm.source = article.source
            orm.status = article.status
            orm.error_message = article.error_message
            orm.document_id = article.document_id
            orm.summary = article.summary
            orm.summary_model = article.summary_model
            orm.summary_updated_at = article.summary_updated_at
            orm.updated_at = _now()
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def set_status(
        self,
        article_id: int,
        status: str,
        error_message: str | None = None,
        document_id: int | None = None,
    ) -> ResearchArticle | None:
        with self._session_factory() as session:
            orm = session.get(ResearchArticleORM, article_id)
            if orm is None:
                return None
            orm.status = status
            orm.error_message = error_message
            if document_id is not None:
                orm.document_id = document_id
            orm.updated_at = _now()
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def set_summary(
        self,
        article_id: int,
        summary: str,
        model: str | None,
    ) -> ResearchArticle | None:
        with self._session_factory() as session:
            orm = session.get(ResearchArticleORM, article_id)
            if orm is None:
                return None
            orm.summary = summary
            orm.summary_model = model
            orm.summary_updated_at = _now()
            orm.updated_at = _now()
            session.commit()
            session.refresh(orm)
            return self._to_entity(orm)

    def delete(self, article_id: int) -> bool:
        with self._session_factory() as session:
            orm = session.get(ResearchArticleORM, article_id)
            if orm is None:
                return False
            session.delete(orm)
            session.commit()
            return True

    def count(
        self,
        library_id: int,
        query: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        status: str | None = None,
    ) -> int:
        with self._session_factory() as session:
            return int(
                session.scalar(
                    select(func.count(ResearchArticleORM.id)).where(
                        *self._conditions(
                            library_id, query, year_from, year_to, status
                        )
                    )
                )
                or 0
            )
