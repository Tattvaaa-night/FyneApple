from __future__ import annotations

import base64
import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ddgs import DDGS
from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

app = Flask(__name__)


MAX_QUERY_LENGTH = 300
MAX_RESULTS = 10

SEARCH_TIMEOUT_SECONDS = 8

IMAGE_TIMEOUT_SECONDS = 6

CACHE_TTL_SECONDS = 120


_search_cache: dict[
    str,
    tuple[
        float,
        list[dict[str, Any]]
    ]
] = {}


_cache_lock = threading.Lock()


def load_local_index() -> list[dict[str, str]]:
    """
    Load the local JSON search index when the server starts.

    The local index is used as a fallback when live web search
    cannot return results.
    """

    try:

        with DATA_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            documents = json.load(
                file
            )

    except FileNotFoundError as exc:

        raise RuntimeError(
            f"Could not find data.json at {DATA_FILE}"
        ) from exc

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "data.json contains invalid JSON."
        ) from exc


    if not isinstance(
        documents,
        list
    ):

        raise RuntimeError(
            "data.json must contain a JSON array."
        )


    required_fields = {
        "title",
        "url",
        "snippet",
        "content",
    }


    cleaned_documents: list[
        dict[str, str]
    ] = []


    for position, document in enumerate(
        documents
    ):

        if not isinstance(
            document,
            dict
        ):

            raise RuntimeError(
                f"Document {position} is not an object."
            )


        missing_fields = (
            required_fields
            - set(document.keys())
        )


        if missing_fields:

            missing_text = ", ".join(
                sorted(
                    missing_fields
                )
            )

            raise RuntimeError(
                f"Document {position} is missing: "
                f"{missing_text}"
            )


        for field in required_fields:

            if not isinstance(
                document[field],
                str
            ):

                raise RuntimeError(
                    f"Document {position} field "
                    f"'{field}' must be a string."
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


def tokenize(
    text: str
) -> list[str]:
    """
    Convert text into lowercase searchable tokens.
    """

    return re.findall(
        r"[a-z0-9]+",
        text.lower()
    )


def clean_query(
    raw_query: str
) -> str:
    """
    Normalize whitespace and remove control characters.
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


    return normalized[
        :MAX_QUERY_LENGTH
    ]


def safe_http_url(
    url: str
) -> str | None:
    """
    Only permit HTTP and HTTPS URLs.
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


def display_url(
    url: str
) -> str:
    """
    Produce a clean URL label for the UI.
    """

    safe_url = safe_http_url(
        url
    )


    if not safe_url:

        return ""


    parsed = urlsplit(
        safe_url
    )


    hostname = parsed.netloc.removeprefix(
        "www."
    )


    path = parsed.path.rstrip(
        "/"
    )


    if path:

        return (
            f"{hostname}{path}"
        )


    return hostname


def local_score(
    query_words: list[str],
    document: dict[str, str]
) -> int:
    """
    Weighted keyword scoring for the JSON fallback index.
    """

    weights = {
        "title": 7,
        "url": 4,
        "snippet": 3,
        "content": 1,
    }


    score = 0


    for word in query_words:

        for field, weight in weights.items():

            field_words = tokenize(
                document[field]
            )


            occurrences = (
                field_words.count(
                    word
                )
            )


            score += (
                occurrences
                * weight
            )


    return score


def search_local(
    query: str
) -> list[dict[str, Any]]:
    """
    Search the JSON fallback index.
    """

    query_words = tokenize(
        query
    )


    if not query_words:

        return []


    results: list[
        dict[str, Any]
    ] = []


    for position, document in enumerate(
        LOCAL_INDEX
    ):

        score = local_score(
            query_words,
            document
        )


        if score <= 0:

            continue


        results.append(
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


    results.sort(
        key=lambda result: (
            -result["score"],
            result["_position"],
        )
    )


    for result in results:

        result.pop(
            "_position",
            None
        )


    return results


def get_cached(
    query: str
) -> list[dict[str, Any]] | None:
    """
    Retrieve a fresh cached search response.
    """

    now = time.monotonic()


    with _cache_lock:

        cached = _search_cache.get(
            query
        )


        if cached is None:

            return None


        created_at, results = cached


        if (
            now - created_at
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
    Store a short-lived search response.
    """

    with _cache_lock:

        _search_cache[query] = (
            time.monotonic(),
            [
                dict(result)
                for result in results
            ],
        )


        if len(
            _search_cache
        ) > 100:

            oldest_query = min(
                _search_cache,
                key=lambda key:
                    _search_cache[key][0]
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
    Additional relevance scoring used to slightly reorder
    upstream web-search results.
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
    Search the live public web.
    """

    cached = get_cached(
        query
    )


    if cached is not None:

        return cached


    query_words = tokenize(
        query
    )


    engine = DDGS(
        timeout=SEARCH_TIMEOUT_SECONDS
    )


    raw_results = engine.text(
        query,
        region="in-en",
        safesearch="moderate",
        max_results=MAX_RESULTS,
        backend="auto",
    )


    results: list[
        dict[str, Any]
    ] = []


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


        key = href.lower()


        if key in seen_urls:

            continue


        seen_urls.add(
            key
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
                "_score": score,
            }
        )


    results.sort(
        key=lambda result:
            -result["_score"]
    )


    for result in results:

        result.pop(
            "_score",
            None
        )


    set_cached(
        query,
        results
    )


    return results


def fetch_image_as_data_url(
    image_url: str
) -> str | None:
    """
    Download a remote image and convert it to a data URL.

    This lets the browser draw the image into a canvas without
    depending on the remote site's CORS policy.
    """

    safe_url = safe_http_url(
        image_url
    )


    if not safe_url:

        return None


    headers = {

        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0 Safari/537.36",

        "Accept":
            "image/avif,image/webp,image/apng,"
            "image/svg+xml,image/*,*/*;q=0.8",

    }


    try:

        image_request = Request(
            safe_url,
            headers=headers
        )


        with urlopen(
            image_request,
            timeout=IMAGE_TIMEOUT_SECONDS
        ) as response:

            content_type = (
                response.headers.get_content_type()
            )


            allowed_types = {
                "image/jpeg",
                "image/png",
                "image/webp",
                "image/gif",
                "image/avif",
            }


            if content_type not in allowed_types:

                return None


            maximum_bytes = 900_000


            image_bytes = response.read(
                maximum_bytes + 1
            )


            if len(image_bytes) > maximum_bytes:

                return None


            encoded = base64.b64encode(
                image_bytes
            ).decode(
                "ascii"
            )


            return (
                f"data:{content_type};"
                f"base64,{encoded}"
            )


    except Exception as exc:

        app.logger.warning(
            "Pixellet image download failed: %s",
            exc
        )


        return None


def search_pixellet_image(
    query: str
) -> dict[str, str] | None:
    """
    Search for an image matching the user's query.
    """

    try:

        engine = DDGS(
            timeout=7
        )


        image_results = engine.images(
            query,
            region="in-en",
            safesearch="moderate",
            max_results=5,
            backend="auto",
        )


    except Exception as exc:

        app.logger.warning(
            "Pixellet image search failed: %s",
            exc
        )


        return None


    for image_result in image_results:

        title = str(
            image_result.get(
                "title",
                ""
            )
        ).strip()


        image_url = str(
            image_result.get(
                "image",
                ""
            )
        ).strip()


        thumbnail_url = str(
            image_result.get(
                "thumbnail",
                ""
            )
        ).strip()


        source_url = str(
            image_result.get(
                "url",
                ""
            )
        ).strip()


        candidates = [
            image_url,
            thumbnail_url,
        ]


        for candidate in candidates:

            if not candidate:

                continue


            data_url = (
                fetch_image_as_data_url(
                    candidate
                )
            )


            if not data_url:

                continue


            return {
                "image": data_url,

                "title":
                    title or query,

                "source":
                    safe_http_url(
                        source_url
                    ) or "",
            }


    return None


@app.get(
    "/api/suggestions"
)
def api_suggestions():
    """
    Generate suggestions from live search results.
    """

    query = clean_query(
        request.args.get(
            "q",
            "",
            type=str
        )
    )


    if len(query) < 2:

        return jsonify([])


    try:

        results = search_web(
            query
        )


    except Exception as exc:

        app.logger.warning(
            "Suggestion request failed: %s",
            exc
        )

        return jsonify([])


    suggestions = []

    seen: set[str] = set()


    for result in results:

        title = str(
            result.get(
                "title",
                ""
            )
        ).strip()


        if not title:

            continue


        key = title.lower()


        if key in seen:

            continue


        seen.add(
            key
        )


        suggestions.append(
            {
                "text": title
            }
        )


        if len(
            suggestions
        ) >= 6:

            break


    return jsonify(
        suggestions
    )


@app.get(
    "/api/pixellet"
)
def api_pixellet():
    """
    Find one image that represents the user's search.
    """

    query = clean_query(
        request.args.get(
            "q",
            "",
            type=str
        )
    )


    if not query:

        return jsonify(
            {
                "error":
                    "A search query is required."
            }
        ), 400


    pixellet = search_pixellet_image(
        query
    )


    if pixellet is None:

        return jsonify(
            {
                "error":
                    "No suitable image was found.",

                "query":
                    query,
            }
        ), 404


    return jsonify(
        {
            "query":
                query,

            **pixellet,
        }
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


    started_at = (
        time.perf_counter()
    )


    live_search_used = False

    message = None

    search_results: list[
        dict[str, Any]
    ] = []


    if query:

        try:

            search_results = search_web(
                query
            )


            if search_results:

                live_search_used = True

            else:

                search_results = search_local(
                    query
                )


                if search_results:

                    message = (
                        "No live results were returned. "
                        "Showing local fallback results."
                    )

        except Exception as exc:

            app.logger.warning(
                "Live search failed: %s",
                exc
            )


            search_results = search_local(
                query
            )


            if search_results:

                message = (
                    "Live web search is temporarily "
                    "unavailable. Showing local "
                    "fallback results."
                )

            else:

                message = (
                    "Live web search is temporarily "
                    "unavailable."
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

        result_count=len(
            search_results
        ),

        live_search_used=
            live_search_used,

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

            message=
                "The page you requested does "
                "not exist.",

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