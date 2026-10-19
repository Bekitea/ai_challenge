"""Нормализация идентификаторов научных статей (DOI, OpenAlex ID)."""

from __future__ import annotations

import re

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_OPENALEX_PREFIXES = (
    "https://openalex.org/",
    "http://openalex.org/",
    "openalex:",
)


def normalize_doi(value: str | None) -> str | None:
    """Приводит DOI к виду ``10.xxxx/yyyy`` (нижний регистр)."""
    if not value:
        return None
    text = value.strip()
    lowered = text.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip().strip("/")
    if not text:
        return None
    return text.lower()


def normalize_openalex_id(value: str | None) -> str | None:
    """Оставляет от OpenAlex ID только суффикс (``W123...``)."""
    if not value:
        return None
    text = value.strip()
    lowered = text.lower()
    for prefix in _OPENALEX_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip().strip("/")
    if not text:
        return None
    match = re.search(r"(W\d+)$", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else text


def identifier_kind(value: str) -> str:
    """Возвращает ``doi``, ``openalex`` или ``unknown``."""
    text = (value or "").strip()
    if not text:
        return "unknown"
    if text.lower().startswith(_DOI_PREFIXES) or text.lower().startswith("10."):
        return "doi"
    if text.lower().startswith(_OPENALEX_PREFIXES):
        return "openalex"
    if re.fullmatch(r"W\d+", text, flags=re.IGNORECASE):
        return "openalex"
    return "unknown"
