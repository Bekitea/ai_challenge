"""Разбор ответов OpenAlex: аннотации, OA-ссылки, фильтры, ошибки."""

import os

os.environ["APPLICATION_MODE"] = "TEST"


from core.infrastructure.research.openalex_client import OpenAlexClient


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = "{}"
        self.headers: dict[str, str] = {}

    def json(self):
        return self._payload


_WORK = {
    "id": "https://openalex.org/W123",
    "doi": "https://doi.org/10.1000/ABC",
    "title": "Deep learning for screening",
    "publication_year": 2023,
    "cited_by_count": 42,
    "language": "en",
    "type": "article",
    "open_access": {"is_oa": True},
    "authorships": [
        {"author": {"display_name": "Jane Doe"}},
        {"author": {"display_name": "John Smith"}},
    ],
    "primary_location": {
        "source": {"display_name": "Journal of Screening"},
        "landing_page_url": "https://example.org/article",
    },
    "best_oa_location": {
        "pdf_url": "https://example.org/article.pdf",
        "landing_page_url": "https://example.org/article",
        "is_oa": True,
    },
    "locations": [],
    "abstract_inverted_index": {
        "Deep": [0],
        "learning": [1],
        "works": [2],
    },
}


def test_search_maps_work_and_reconstructs_abstract(monkeypatch):
    captured: dict = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"results": [_WORK]})

    monkeypatch.setattr(
        "core.infrastructure.research.openalex_client.requests.get", fake_get
    )
    client = OpenAlexClient(base_url="http://test", mailto="me@example.com", rps=1000)

    articles = client.search("screening", year_from=2020, year_to=2024, limit=10)

    assert len(articles) == 1
    article = articles[0]
    assert article.title == "Deep learning for screening"
    assert article.doi == "10.1000/abc"
    assert article.openalex_id == "W123"
    assert article.authors == ["Jane Doe", "John Smith"]
    assert article.abstract == "Deep learning works"
    assert article.pdf_url == "https://example.org/article.pdf"
    assert article.is_open_access is True
    assert captured["params"]["filter"] == (
        "type:article,is_oa:true,from_publication_date:2020-01-01,"
        "to_publication_date:2024-12-31"
    )
    assert captured["params"]["search"] == "screening"
    assert captured["params"]["mailto"] == "me@example.com"


def test_get_by_identifier_uses_doi_filter(monkeypatch):
    captured: dict = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse({"results": [_WORK]})

    monkeypatch.setattr(
        "core.infrastructure.research.openalex_client.requests.get", fake_get
    )
    client = OpenAlexClient(base_url="http://test", rps=1000)

    article = client.get_by_identifier("https://doi.org/10.1000/ABC")

    assert article is not None
    assert article.doi == "10.1000/abc"
    assert captured["params"]["filter"] == "doi:10.1000/abc"


def test_get_by_identifier_returns_none_for_unknown_doi(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse({"results": []})

    monkeypatch.setattr(
        "core.infrastructure.research.openalex_client.requests.get", fake_get
    )
    client = OpenAlexClient(base_url="http://test", rps=1000)

    assert client.get_by_identifier("10.9999/unknown") is None


def test_search_requires_query():
    client = OpenAlexClient(base_url="http://test", rps=1000)
    assert client.search("   ") == []
