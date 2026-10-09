"""Shared helpers and errors for public job-source adapters."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from app.models.job import WorkMode


class JobSourceError(Exception):
    """Raised when an external job source cannot be queried or parsed."""


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
    value = location.casefold()
    if "sweden" in value or "sverige" in value:
        return "Sweden"
    if "norway" in value or "norge" in value:
        return "Norway"
    if "denmark" in value or "danmark" in value:
        return "Denmark"
    if "finland" in value or "suomi" in value:
        return "Finland"
    if "germany" in value or "deutschland" in value:
        return "Germany"
    return default_country.strip()


def make_job_id(source: str, source_id: str) -> str:
    safe_source_id = re.sub(r"[^A-Za-z0-9._:-]+", "-", source_id.strip())
    return f"{source}:{safe_source_id or 'unknown'}"
