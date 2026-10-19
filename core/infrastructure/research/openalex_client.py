from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

import config
from core.application.dtos.article_candidate_dto import ArticleCandidateDTO
from core.application.exceptions.research_source_error import ResearchSourceError
from core.application.services.research_identifiers import (
    normalize_doi,
    normalize_openalex_id,
)

logger = logging.getLogger("research.openalex")

_SORT_OPTIONS = {
    "relevance": "relevance_score:desc",
    "cited": "cited_by_count:desc",
    "recent": "publication_date:desc",
}


class _RateLimiter:
    """Простой ограничитель частоты запросов (не более N в секунду)."""

    def __init__(self, rps: float):
        self._min_interval = 1.0 / max(rps, 0.1)
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._last_request + self._min_interval - now
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()


class OpenAlexClient:
    """Клиент OpenAlex: поиск работ и получение метаданных по DOI/ID."""

    def __init__(
        self,
        base_url: str | None = None,
        mailto: str | None = None,
        rps: float | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ):
        self._base_url = (base_url or config.OPENALEX_API_URL).rstrip("/")
        self._mailto = (mailto if mailto is not None else config.OPENALEX_MAILTO).strip()
        self._timeout = timeout or config.OPENALEX_TIMEOUT
        self._max_retries = max(1, max_retries or config.OPENALEX_MAX_RETRIES)
        self._limiter = _RateLimiter(rps if rps is not None else config.OPENALEX_RPS)

    def _headers(self) -> dict[str, str]:
        mailto = self._mailto or "anonymous"
        return {
            "User-Agent": f"ai-chat-research/1.0 (mailto:{mailto})",
            "Accept": "application/json",
        }

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._limiter.wait()
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self._max_retries:
                    break
                time.sleep(min(2**attempt, 30))
                continue

            if response.status_code == 404:
                return {}
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = float(retry_after) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                delay = max(1.0, min(delay, 60.0))
                logger.warning(
                    "OpenAlex HTTP %s, повтор через %.1f с (попытка %s/%s)",
                    response.status_code,
                    delay,
                    attempt,
                    self._max_retries,
                )
                if attempt == self._max_retries:
                    raise ResearchSourceError(
                        f"OpenAlex вернул HTTP {response.status_code}. "
                        f"Ответ: {response.text[:300]}"
                    )
                time.sleep(delay)
                continue

            if not response.ok:
                raise ResearchSourceError(
                    f"OpenAlex вернул HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise ResearchSourceError(
                    "OpenAlex вернул некорректный JSON."
                ) from exc
            return data if isinstance(data, dict) else {}

        raise ResearchSourceError(
            f"Не удалось выполнить запрос к OpenAlex: {last_error}"
        )

    def search(
        self,
        query: str,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 20,
        sort: str = "relevance",
        language: str | None = None,
        oa_only: bool = True,
    ) -> list[ArticleCandidateDTO]:
        clean_query = (query or "").strip()
        if not clean_query:
            return []

        filters = ["type:article"]
        if oa_only:
            filters.append("is_oa:true")
        if year_from is not None:
            filters.append(f"from_publication_date:{int(year_from)}-01-01")
        if year_to is not None:
            filters.append(f"to_publication_date:{int(year_to)}-12-31")
        if language:
            filters.append(f"language:{language}")

        params: dict[str, Any] = {
            "search": clean_query,
            "filter": ",".join(filters),
            "per-page": max(1, min(int(limit), 50)),
        }
        if self._mailto:
            params["mailto"] = self._mailto
        sort_value = _SORT_OPTIONS.get(sort)
        if sort_value:
            params["sort"] = sort_value

        data = self._get(f"{self._base_url}/works", params)
        results = data.get("results") or []
        articles: list[ArticleCandidateDTO] = []
        for work in results:
            candidate = self._to_candidate(work)
            if candidate is not None:
                articles.append(candidate)
        return articles

    def get_by_identifier(self, identifier: str) -> ArticleCandidateDTO | None:
        text = (identifier or "").strip()
        if not text:
            return None

        openalex_id = normalize_openalex_id(text)
        if openalex_id and openalex_id.upper().startswith("W"):
            data = self._get(f"{self._base_url}/works/{openalex_id}", {})
            return self._to_candidate(data) if data else None

        doi = normalize_doi(text)
        if not doi:
            return None
        params: dict[str, Any] = {
            "filter": f"doi:{doi}",
            "per-page": 1,
        }
        if self._mailto:
            params["mailto"] = self._mailto
        data = self._get(f"{self._base_url}/works", params)
        results = data.get("results") or []
        if not results:
            return None
        return self._to_candidate(results[0])

    @staticmethod
    def _reconstruct_abstract(inverted: Any) -> str | None:
        if not isinstance(inverted, dict) or not inverted:
            return None
        positioned: list[tuple[int, str]] = []
        for word, positions in inverted.items():
            if not isinstance(positions, list):
                continue
            for position in positions:
                if isinstance(position, int):
                    positioned.append((position, str(word)))
        if not positioned:
            return None
        positioned.sort(key=lambda item: item[0])
        return " ".join(word for _, word in positioned)

    @classmethod
    def _to_candidate(cls, work: dict[str, Any]) -> ArticleCandidateDTO | None:
        if not isinstance(work, dict) or not work:
            return None
        title = (work.get("title") or work.get("display_name") or "").strip()
        if not title:
            return None

        authors: list[str] = []
        for authorship in work.get("authorships") or []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author") or {}
            name = (author.get("display_name") or "").strip()
            if name:
                authors.append(name)

        primary = work.get("primary_location") or {}
        source = (primary.get("source") or {}) if isinstance(primary, dict) else {}
        venue = (
            source.get("display_name")
            or source.get("host_organization_name")
            or None
        )

        best_oa = work.get("best_oa_location") or {}
        locations = work.get("locations") or []
        pdf_url = None
        landing_url = None
        is_oa = bool((work.get("open_access") or {}).get("is_oa"))
        if isinstance(best_oa, dict):
            pdf_url = best_oa.get("pdf_url")
            landing_url = best_oa.get("landing_page_url")
            is_oa = is_oa or bool(best_oa.get("is_oa"))
        if not pdf_url:
            for location in locations:
                if not isinstance(location, dict):
                    continue
                if location.get("pdf_url"):
                    pdf_url = location.get("pdf_url")
                    is_oa = is_oa or bool(location.get("is_oa"))
                    break
        if not landing_url:
            landing_url = (
                (primary.get("landing_page_url") if isinstance(primary, dict) else None)
                or work.get("id")
            )

        openalex_id = normalize_openalex_id(work.get("id"))
        return ArticleCandidateDTO(
            title=title,
            openalex_id=openalex_id,
            doi=normalize_doi(work.get("doi")),
            authors=authors,
            publication_year=work.get("publication_year"),
            venue=venue,
            language=work.get("language"),
            abstract=cls._reconstruct_abstract(
                work.get("abstract_inverted_index")
            ),
            cited_by_count=work.get("cited_by_count"),
            is_open_access=is_oa,
            pdf_url=pdf_url,
            landing_url=landing_url,
            source="openalex",
        )
