#!/usr/bin/env python3

import os
import sys
import threading
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from mcp.server import MCPServer
from pydantic import BaseModel

load_dotenv()

MAILTO = os.getenv("OPENALEX_MAILTO", "you@example.com")
RPS = float(os.getenv("OPENALEX_RPS", "5"))
MAX_RETRIES = int(os.getenv("OPENALEX_MAX_RETRIES", "5"))
URL = "https://api.openalex.org/"

mcp = MCPServer("OpenAlexSearch")


class RateLimiter:
    def __init__(self, rps: float):
        if rps <= 0:
            rps = 1.0
        self.min_interval = 1.0 / rps
        self.last_request_time = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            wait_seconds = self.last_request_time + self.min_interval - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self.last_request_time = time.monotonic()


rate_limiter = RateLimiter(RPS)


def fetch_with_retries(url: str, params: dict, headers: dict) -> requests.Response:
    """
    Делает GET-запрос с ограничением частоты и повторами при 429/5xx.
    """
    response = None

    for attempt in range(1, MAX_RETRIES + 1):
        rate_limiter.wait()

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            print(f"Сетевая ошибка: {exc}", file=sys.stderr)

            if attempt == MAX_RETRIES:
                raise

            delay = min(2**attempt, 60)
            print(f"Повтор через {delay} секунд...", file=sys.stderr)
            time.sleep(delay)
            continue

        if response.status_code >= 500:
            retry_after = response.headers.get("Retry-After")

            try:
                delay = float(retry_after) if retry_after else 2**attempt
            except ValueError:
                delay = 2**attempt

            delay = max(1.0, min(delay, 120.0))

            print(
                f"HTTP {response.status_code}. "
                f"Повтор через {delay:.1f} секунд "
                f"(попытка {attempt}/{MAX_RETRIES}).",
                file=sys.stderr,
            )

            time.sleep(delay)
            continue

        return response

    return response


class AuthorInfo(BaseModel):
    display_name: str


class AuthorshipInfo(BaseModel):
    author: AuthorInfo


class WorkResult(BaseModel):
    title: str | None = None
    doi: str | None = None
    publication_year: int | None = None
    authorships: list[AuthorshipInfo] | None = None


class MetaInfo(BaseModel):
    count: int


class OpenAlexResponse(BaseModel):
    meta: MetaInfo
    results: list[WorkResult]


@dataclass
class Article:
    title: str
    doi: str
    authors: list[str]
    year: int | None = None

    def __str__(self) -> str:
        authors_str = ", ".join(self.authors) if self.authors else "Авторы не указаны"
        year_str = str(self.year) if self.year else "Неизвестен"
        return (
            f"Название: {self.title}\n"
            f"DOI: {self.doi}\n"
            f"Год: {year_str}\n"
            f"Авторы: {authors_str}\n"
        )


def _search_articles_impl(keywords: list[str], year: int) -> list[Article]:
    """
    Формирует OQL-запрос по массиву слов и году, отправляет его в OpenAlex,
    валидирует ответ через Pydantic и возвращает массив объектов Article.
    """
    keywords_query = " and ".join(keywords)
    oql = (
        "works where has DOI is (true) "
        "and open access is (true) "
        "and has ISSN is (true) "
        f"and year >= ({year}) "
        f"and title/abstract has ({keywords_query}) "
        "and type is (article)"
    )

    params = {
        "oql": oql,
        "per-page": 10,
        "sort": "cited_by_count:desc",
        "mailto": MAILTO,
        "select": "title,authorships,doi,publication_year",
    }

    headers = {
        "User-Agent": f"openalex-oql-script/1.0 (mailto:{MAILTO})",
        "Accept": "application/json",
    }

    response = fetch_with_retries(URL, params, headers)

    if not response or not response.ok:
        error_text = response.text if response else "Нет ответа"
        status = response.status_code if response else "N/A"
        raise RuntimeError(f"Ошибка HTTP {status}: {error_text}")

    parsed_data = OpenAlexResponse.model_validate(response.json())

    articles = []
    for work in parsed_data.results:
        authors = [
            authorship.author.display_name
            for authorship in (work.authorships or [])
            if authorship.author and authorship.author.display_name
        ]
        articles.append(
            Article(
                title=work.title or "Без названия",
                doi=work.doi or "Без DOI",
                authors=authors,
                year=work.publication_year,
            )
        )

    return articles


@mcp.tool()
def search_articles(keywords: list[str], year: int = 2020) -> str:
    """
    Поиск научных статей по ключевым словам через OpenAlex API.

    Параметры:
        keywords: Список ключевых слов для поиска.
        year: Минимальный год публикации (по умолчанию 2020).

    Возвращает список найденных статей с их годами публикации.
    """
    try:
        articles = _search_articles_impl(keywords, year)
        if not articles:
            return "Статьи не найдены."

        result = f"Найдено статей: {len(articles)}\n{'=' * 50}\n"
        for article in articles:
            result += str(article) + "\n"
        return result
    except Exception as exc:  # noqa: BLE001
        return f"Не удалось выполнить запрос: {exc}"


if __name__ == "__main__":
    # Запускаем сервер, используя транспорт stdio
    mcp.run(transport="stdio")
