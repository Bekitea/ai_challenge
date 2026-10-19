from __future__ import annotations

import logging
from typing import Any

import requests

import config
from core.application.services.research_identifiers import normalize_doi

logger = logging.getLogger("research.unpaywall")


class UnpaywallClient:
    """Fallback-поиск OA-PDF по DOI через Unpaywall API."""

    def __init__(
        self,
        email: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ):
        self._email = (email if email is not None else config.UNPAYWALL_EMAIL).strip()
        self._base_url = (base_url or config.UNPAYWALL_API_URL).rstrip("/")
        self._timeout = timeout or config.UNPAYWALL_TIMEOUT

    def find_pdf_url(self, doi: str | None) -> str | None:
        normalized = normalize_doi(doi)
        if not normalized or not self._email:
            return None
        try:
            response = requests.get(
                f"{self._base_url}/{normalized}",
                params={"email": self._email},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Unpaywall недоступен: %s", exc)
            return None
        if not response.ok:
            return None
        try:
            data: Any = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None

        best = data.get("best_oa_location") or {}
        pdf_url = self._pdf_from_location(best)
        if pdf_url:
            return pdf_url
        for location in data.get("oa_locations") or []:
            pdf_url = self._pdf_from_location(location)
            if pdf_url:
                return pdf_url
        return None

    @staticmethod
    def _pdf_from_location(location: Any) -> str | None:
        if not isinstance(location, dict):
            return None
        return location.get("url_for_pdf")
