"""Shared helpers and errors for public job-source adapters."""

from __future__ import annotations

import html
import re
import time
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.job import WorkMode


class JobSourceError(Exception):
    """Raised when an external job source cannot be queried or parsed."""


_RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=8.0)

def get_with_retries(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | float | None = None,
    max_attempts: int = 3,
) -> httpx.Response:
    """Perform a bounded GET with retries for transient network failures.

    Retries are deliberately limited to timeouts/transport errors and common
    transient HTTP responses. Authentication and other client errors are not
    retried. A short, bounded delay avoids hammering a provider that is
    rate-limiting the local application.
    """
    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be between 1 and 5")

    request_timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT
    for attempt in range(max_attempts):
        try:
            response = httpx.get(
                url, params=params, headers=headers, timeout=request_timeout
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code in _RETRYABLE_HTTP_STATUS_CODES
            if not retryable or attempt + 1 >= max_attempts:
                raise
            retry_after = exc.response.headers.get("Retry-After", "")
            try:
                delay = min(2.0, max(0.0, float(retry_after)))
            except (TypeError, ValueError):
                delay = 0.25 * (2 ** attempt)
            time.sleep(delay)
        except httpx.RequestError:
            if attempt + 1 >= max_attempts:
                raise
            time.sleep(0.25 * (2 ** attempt))

    # The loop either returns or re-raises; this is an unreachable guard.
    raise RuntimeError("HTTP retry loop ended unexpectedly")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def clean_html(value: Any) -> str:
    """Convert HTML-ish job description content into readable plain text."""
    if not isinstance(value, str) or not value.strip():
        return ""
    # Some feeds double-escape HTML; unescape twice before stripping tags.
    text = html.unescape(html.unescape(value))
    parser = _TextExtractor()
    try:
        parser.feed(text)
        parser.close()
        return " ".join(parser.parts).strip()
    except Exception:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text)).strip()


def safe_http_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return ""
    return value


def text_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict):
        for key in ("name", "label", "value", "text"):
            result = text_value(value.get(key))
            if result:
                return result
    return ""


def classify_work_mode(*values: Any) -> WorkMode:
    """Infer work mode only from explicit source fields or plain-text evidence."""
    text = " ".join(text_value(value) for value in values).casefold()
    text = re.sub(r"\s+", " ", text)
    if re.search(r"\bhybrid\b|\bhybridarbete\b|\bdelvis distansarbete\b|\bkombinerat distansarbete\b", text):
        return "hybrid"
    if re.search(r"\bremote\b|\bfully remote\b|\bremote-first\b|\bwork from home\b|\bworking from home\b|\bdistansarbete\b|\barbeta på distans\b|\bhemifrån\b", text):
        return "remote"
    if re.search(r"\bon[- ]site\b|\bin-office\b|\bpå plats\b|\bpå kontoret\b|\bfysiskt på kontor\b", text):
        return "on_site"
    return "unknown"


def infer_country(location: str, default_country: str = "") -> str:
    """Infer a country only from recognizable location text, otherwise use the configured default."""
    value = re.sub(r"\s+", " ", location.casefold()).strip()
    country_markers = (
        ("Sweden", ("sweden", "sverige", "swedish")),
        ("Norway", ("norway", "norge", "norwegian")),
        ("Denmark", ("denmark", "danmark", "danish")),
        ("Finland", ("finland", "suomi", "finnish")),
        ("Germany", ("germany", "deutschland", "german")),
        ("Netherlands", ("netherlands", "the netherlands", "dutch", "holland")),
        ("United Kingdom", ("united kingdom", "uk only", "uk", "britain", "england", "scotland", "wales")),
        ("United States", ("united states", "usa", "us only", "u.s.", "american")),
        ("Canada", ("canada", "canadian")),
        ("Ireland", ("ireland", "irish")),
        ("France", ("france", "french")),
        ("Spain", ("spain", "spanish")),
        ("Italy", ("italy", "italian")),
        ("Poland", ("poland", "polish")),
        ("Estonia", ("estonia", "estonian")),
        ("Switzerland", ("switzerland", "swiss")),
        ("Austria", ("austria", "austrian")),
        ("Portugal", ("portugal", "portuguese")),
        ("Belgium", ("belgium", "belgian")),
        ("Iceland", ("iceland", "icelandic")),
        ("Australia", ("australia", "australian")),
        ("New Zealand", ("new zealand",)),
        ("India", ("india", "indian")),
        ("Singapore", ("singapore",)),
    )
    for country, markers in country_markers:
        for marker in markers:
            if marker in value and (marker not in {"uk", "usa"} or re.search(rf"\b{re.escape(marker)}\b", value)):
                return country
    return default_country.strip()


def make_job_id(source: str, source_id: str) -> str:
    safe_source_id = re.sub(r"[^A-Za-z0-9._:-]+", "-", source_id.strip())
    return f"{source}:{safe_source_id or 'unknown'}"
