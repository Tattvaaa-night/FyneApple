from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ddgs import DDGS
from flask import Flask, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

app = Flask(__name__)

MAX_QUERY_LENGTH = 300
MAX_RESULTS = 10
SEARCH_TIMEOUT_SECONDS = 8
CACHE_TTL_SECONDS = 120


_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_cache_lock = threading.Lock()


def load_local_index() -> list[dict[str, str]]:
    """
    Load the local JSON index when the application starts.

    The JSON index is used as a fallback if the live web search service
    cannot be reached.
    """
    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            documents = json.load(file)

    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Could not find the search index: {DATA_FILE}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"data.json contains invalid JSON: {DATA_FILE}"
        ) from exc

    if not isinstance(documents, list):
        raise RuntimeError(
            "data.json must contain a JSON array."
        )

    required_fields = {
        "title",
        "url",
        "snippet",
        "content",
    }

    cleaned_documents: list[dict[str, str]] = []

    for position, document in enumerate(documents):

        if not isinstance(document, dict):
            raise RuntimeError(
                f"Document {position} is not a JSON object."
            )

        missing_fields = required_fields - set(document.keys())

        if missing_fields:
            missing_text = ", ".join(
                sorted(missing_fields)
            )

            raise RuntimeError(
                f"Document {position} is missing: {missing_text}"
            )

        for field in required_fields:

            if not isinstance(document[field], str):
                raise RuntimeError(
                    f"Document {position} field '{field}' "
                    "must contain a string."
                )

        cleaned_documents.append(
            {
                "title": document["title"].strip(),
                "url": document["url"].strip(),
                "snippet": document["snippet"].strip(),
                "content": document["content"].strip(),
            }
        )

    return cleaned_documents


LOCAL_INDEX = load_local_index()


def tokenize(text: str) -> list[str]:
    """
    Turn text into lowercase searchable words.
    """
    return re.findall(
        r"[a-z0-9]+",
        text.lower()
    )


def clean_query(raw_query: str) -> str:
    """
    Clean user input and prevent unnecessarily large requests.
    """
    normalized = re.sub(
        r"[\x00-\x1f\x7f]",
        " ",
        raw_query
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    ).strip()

    return normalized[:MAX_QUERY_LENGTH]


def safe_http_url(url: str) -> str | None:
    """
    Only allow HTTP and HTTPS result URLs.
    """
    try:
        parsed = urlsplit(
            url.strip()
        )
    except ValueError:
        return None

    if parsed.scheme.lower() not in {
        "http",
        "https",
    }:
        return None

    if not parsed.netloc:
        return None

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.query,
            "",
        )
    )


def display_url(url: str) -> str:
    """
    Convert a full URL into a compact display version.
    """
    safe_url = safe_http_url(url)

    if safe_url is None:
        return ""

    parsed = urlsplit(
        safe_url
    )

    host = parsed.netloc.removeprefix(
        "www."
    )

    path = parsed.path.rstrip("/")

    if path:
        return f"{host}{path}"

    return host


def local_score(
    query_words: list[str],
    document: dict[str, str]
) -> int:
    """
    Score local fallback documents.

    Title:
        weight 7

    URL:
        weight 4

    Snippet:
        weight 3

    Content:
        weight 1
    """
    field_weights = {
        "title": 7,
        "url": 4,
        "snippet": 3,
        "content": 1,
    }

    score = 0

    for word in query_words:

        for field_name, weight in field_weights.items():

            field_words = tokenize(
                document[field_name]
            )

            occurrences = field_words.count(
                word
            )

            score += occurrences * weight

    return score


def search_local(
    query: str
) -> list[dict[str, Any]]:
    """
    Search the local JSON fallback index.
    """
    query_words = tokenize(
        query
    )

    if not query_words:
        return []

    matches: list[dict[str, Any]] = []

    for position, document in enumerate(
        LOCAL_INDEX
    ):

        score = local_score(
            query_words,
            document
        )

        if score <= 0:
            continue

        matches.append(
            {
                "title": document["title"],
                "url": safe_http_url(
                    document["url"]
                ) or "",
                "display_url": display_url(
                    document["url"]
                ),
                "snippet": document["snippet"],
                "score": score,
                "_position": position,
            }
        )

    matches.sort(
        key=lambda result: (
            -result["score"],
            result["_position"],
        )
    )

    for result in matches:
        result.pop(
            "_position",
            None
        )

    return matches


def get_cached(
    query: str
) -> list[dict[str, Any]] | None:
    """
    Return a cached response when it is still fresh.
    """
    now = time.monotonic()

    with _cache_lock:

        cached = _search_cache.get(
            query
        )

        if cached is None:
            return None

        timestamp, results = cached

        if (
            now - timestamp
            > CACHE_TTL_SECONDS
        ):
            _search_cache.pop(
                query,
                None
            )

            return None

        return [
            dict(result)
            for result in results
        ]


def set_cached(
    query: str,
    results: list[dict[str, Any]]
) -> None:
    """
    Store a short-lived cached response.
    """
    with _cache_lock:

        _search_cache[query] = (
            time.monotonic(),
            [
                dict(result)
                for result in results
            ],
        )

        if len(_search_cache) > 100:

            oldest_query = min(
                _search_cache,
                key=lambda key: (
                    _search_cache[key][0]
                )
            )

            _search_cache.pop(
                oldest_query,
                None
            )


def relevance_score(
    query_words: list[str],
    title: str,
    url: str,
    snippet: str
) -> int:
    """
    Add a small deterministic relevance boost to the upstream
    web-search ordering.

    This does not attempt to replace the search provider's ranking.
    It simply rewards exact query-word appearances in important fields.
    """
    title_words = tokenize(
        title
    )

    url_words = tokenize(
        url
    )

    snippet_words = tokenize(
        snippet
    )

    score = 0

    for word in query_words:

        score += (
            title_words.count(word)
            * 6
        )

        score += (
            url_words.count(word)
            * 3
        )

        score += (
            snippet_words.count(word)
            * 2
        )

    return score


def search_web(
    query: str
) -> list[dict[str, Any]]:
    """
    Search the live public web through ddgs.
    """
    cached = get_cached(
        query
    )

    if cached is not None:
        return cached

    query_words = tokenize(
        query
    )

    search_engine = DDGS(
        timeout=SEARCH_TIMEOUT_SECONDS
    )

    raw_results = search_engine.text(
        query,
        region="in-en",
        safesearch="moderate",
        max_results=MAX_RESULTS,
        backend="auto",
    )

    results: list[dict[str, Any]] = []

    seen_urls: set[str] = set()

    for raw in raw_results:

        title = str(
            raw.get(
                "title",
                ""
            )
        ).strip()

        href = safe_http_url(
            str(
                raw.get(
                    "href",
                    ""
                )
            ).strip()
        )

        body = str(
            raw.get(
                "body",
                ""
            )
        ).strip()

        if not title:
            continue

        if not href:
            continue

        if not body:
            continue

        canonical_url = href.lower()

        if canonical_url in seen_urls:
            continue

        seen_urls.add(
            canonical_url
        )

        score = relevance_score(
            query_words,
            title,
            href,
            body,
        )

        results.append(
            {
                "title": title,
                "url": href,
                "display_url": display_url(
                    href
                ),
                "snippet": body,
                "_relevance": score,
            }
        )

    results.sort(
        key=lambda result: (
            -result["_relevance"]
        )
    )

    for result in results:
        result.pop(
            "_relevance",
            None
        )

    set_cached(
        query,
        results
    )

    return results


def perform_search(
    query: str
) -> tuple[
    list[dict[str, Any]],
    bool,
    str | None
]:
    """
    Search the live web first.

    If live search fails, use the local JSON index.
    """
    if not query:
        return (
            [],
            False,
            None
        )

    try:

        live_results = search_web(
            query
        )

        if live_results:
            return (
                live_results,
                True,
                None
            )

    except Exception as exc:

        app.logger.warning(
            "Live web search failed: %s",
            exc
        )

        fallback_results = search_local(
            query
        )

        if fallback_results:

            return (
                fallback_results,
                False,
                "Live web search is temporarily unavailable. "
                "Showing local fallback results."
            )

        return (
            [],
            False,
            "Live web search is temporarily unavailable."
        )

    fallback_results = search_local(
        query
    )

    if fallback_results:

        return (
            fallback_results,
            False,
            "No live results were returned. "
            "Showing local fallback results."
        )

    return (
        [],
        True,
        None
    )


@app.get("/")
def home():
    return render_template(
        "index.html"
    )


@app.get("/search")
def results():

    raw_query = request.args.get(
        "q",
        "",
        type=str
    )

    query = clean_query(
        raw_query
    )

    started_at = time.perf_counter()

    search_results, live_search_used, message = perform_search(
        query
    )

    elapsed_ms = round(
        (
            time.perf_counter()
            - started_at
        ) * 1000
    )

    return render_template(
        "search.html",
        query=query,
        results=search_results,
        result_count=len(search_results),
        live_search_used=live_search_used,
        message=message,
        elapsed_ms=elapsed_ms,
    )


@app.errorhandler(404)
def not_found(_error):

    return (
        render_template(
            "search.html",
            query="",
            results=[],
            result_count=0,
            live_search_used=False,
            message="The page you requested does not exist.",
            elapsed_ms=0,
        ),
        404,
    )


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )