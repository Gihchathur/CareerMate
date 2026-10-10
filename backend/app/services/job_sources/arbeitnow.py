"""Adapter for Arbeitnow's documented public job-board API.

The API asks downstream clients to link back to the relevant Arbeitnow listing.
CareerMate keeps that URL as both the source and apply link, and labels the
provider in the UI. Results are cached on disk for six hours to limit requests.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    classify_work_mode,
    clean_html,
    get_with_retries,
    infer_country,
    make_job_id,
    safe_http_url,
    text_value,
)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
CACHE_PATH = Path(__file__).resolve().parents[4] / "data" / "source_cache" / "arbeitnow.json"
CACHE_TTL_SECONDS = 6 * 60 * 60
MAX_PAGES = 3
logger = logging.getLogger(__name__)

_COUNTRY_MARKERS = {
    "Germany": ("germany", "deutschland", "german"),
    "United Kingdom": ("united kingdom", "uk", "britain", "england", "scotland", "wales"),
    "France": ("france", "french"),
    "Switzerland": ("switzerland", "schweiz", "swiss"),
    "Austria": ("austria", "österreich", "austrian"),
    "Netherlands": ("netherlands", "the netherlands", "holland", "dutch"),
    "Belgium": ("belgium", "belgian"),
    "Ireland": ("ireland", "irish"),
    "Spain": ("spain", "spanish"),
    "Italy": ("italy", "italian"),
    "Portugal": ("portugal", "portuguese"),
    "Sweden": ("sweden", "sverige", "swedish"),
    "Norway": ("norway", "norge", "norwegian"),
    "Denmark": ("denmark", "danmark", "danish"),
    "Finland": ("finland", "suomi", "finnish"),
    "United States": ("united states", "usa", "u.s."),
    "Canada": ("canada", "canadian"),
}


def _country_from_source(raw: dict[str, Any], location: str, description: str) -> str:
    """Infer country from explicit location, known Arbeitnow domains, or footer.

    The base .com feed includes listing links for several local Arbeitnow sites;
    those domains are a stronger signal than a generic city-only location.
    The Germany fallback applies only to the base .com feed, not the .co.uk/.fr/.ch
    sites. Unknown geography remains blank where no reliable signal exists.
    """
    location_country = infer_country(location, "")
    if location_country:
        return location_country

    url = safe_http_url(raw.get("url"))
    host = (urlparse(url).hostname or "").casefold()
    host_countries = {
        "arbeitnow.co.uk": "United Kingdom",
        "www.arbeitnow.co.uk": "United Kingdom",
        "arbeitnow.uk": "United Kingdom",
        "www.arbeitnow.uk": "United Kingdom",
        "arbeitnow.fr": "France",
        "www.arbeitnow.fr": "France",
        "arbeitnow.ch": "Switzerland",
        "www.arbeitnow.ch": "Switzerland",
    }
    if host in host_countries:
        return host_countries[host]

    # The listing description commonly contains an explicit provider footer such as
    # "Jobs in Germany on Arbeitnow". Match that footer only, not arbitrary prose.
    footer_match = re.search(
        r"(?:find(?: more)?\s+)?jobs\s+in\s+([a-z\s]+?)\s+on\s+arbeitnow\b",
        description.casefold(),
    )
    if footer_match:
        footer_country = " ".join(footer_match.group(1).split()).strip()
        aliases = {
            "germany": "Germany", "united kingdom": "United Kingdom", "uk": "United Kingdom",
            "france": "France", "switzerland": "Switzerland", "the netherlands": "Netherlands",
            "netherlands": "Netherlands", "austria": "Austria", "ireland": "Ireland",
            "spain": "Spain", "italy": "Italy", "portugal": "Portugal", "belgium": "Belgium",
        }
        if footer_country in aliases:
            return aliases[footer_country]

    # For the primary .com feed, many listings are local Germany jobs and only
    # identify their city. Do not assign that fallback to other regional sites.
    if host in {"arbeitnow.com", "www.arbeitnow.com"}:
        return "Germany"
    return ""


def _published_at(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    return text_value(value)


def normalize_job(raw: dict[str, Any]) -> JobPosting:
    """Normalize an Arbeitnow API item into CareerMate's common job model."""
    title = text_value(raw.get("title")) or "Untitled position"
    company = text_value(raw.get("company_name")) or "Company not specified"
    location = text_value(raw.get("location")) or "Location not specified"
    source_url = safe_http_url(raw.get("url"))
    description = clean_html(raw.get("description"))
    tags = raw.get("tags")
    if isinstance(tags, list):
        tag_text = ", ".join(text_value(item) for item in tags if text_value(item))
        if tag_text:
            description = f"Tags: {tag_text}\n\n{description}".strip()
    job_types = raw.get("job_types")
    if isinstance(job_types, list):
        type_text = ", ".join(text_value(item) for item in job_types if text_value(item))
        if type_text:
            description = f"Job type: {type_text}\n\n{description}".strip()

    source_id = text_value(raw.get("slug")) or text_value(raw.get("id")) or source_url
    if not source_id:
        source_id = f"{company}:{title}:{location}"

    if raw.get("remote") is True:
        work_mode = "remote"
    else:
        work_mode = classify_work_mode(location, title, description, tags if isinstance(tags, list) else [])

    country = _country_from_source(raw, location, description)
    if any(marker in location.casefold() for marker in ("worldwide", "anywhere", "global")):
        country = "Worldwide"

    return JobPosting(
        id=make_job_id("arbeitnow", source_id),
        source="arbeitnow",
        source_id=source_id,
        title=title,
        company=company,
        location=location,
        description=description[:30000],
        published_at=_published_at(raw.get("created_at")),
        source_url=source_url,
        apply_url=source_url,
        city=location.split(",", 1)[0].strip() if location else "",
        country=country,
        work_mode=work_mode,
    )


def _load_fresh_cache(now: float) -> list[JobPosting] | None:
    try:
        if not CACHE_PATH.exists():
            return None
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(cached, dict) or not isinstance(cached.get("jobs"), list):
            return None
        fetched_at = float(cached.get("fetched_at", 0))
        if fetched_at <= 0 or now - fetched_at >= CACHE_TTL_SECONDS:
            return None
        return [JobPosting.model_validate(item) for item in cached["jobs"] if isinstance(item, dict)]
    except (OSError, ValueError, TypeError):
        return None


def _write_cache(jobs: list[JobPosting], now: float) -> None:
    path = CACHE_PATH
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps({"fetched_at": now, "jobs": [job.model_dump() for job in jobs]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)
    except OSError:
        # A cache write failure should not discard freshly retrieved search results.
        logger.warning("Could not write the local Arbeitnow cache", exc_info=True)
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def fetch_jobs(*, now: float | None = None) -> list[JobPosting]:
    """Retrieve a small bounded number of pages, caching the normalized data."""
    timestamp = time.time() if now is None else now
    cached_jobs = _load_fresh_cache(timestamp)
    if cached_jobs is not None:
        return cached_jobs

    raw_jobs: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        try:
            response = get_with_retries(
                API_URL,
                params={"page": page},
                headers={"accept": "application/json", "user-agent": "CareerMate-local/0.1 (public job API client)"},
                timeout=httpx.Timeout(20.0, connect=8.0),
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise JobSourceError("Arbeitnow timed out. Please try again later.") from exc
        except httpx.HTTPStatusError as exc:
            raise JobSourceError(f"Arbeitnow returned HTTP {exc.response.status_code}.") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise JobSourceError("Could not retrieve valid data from Arbeitnow.") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise JobSourceError("Arbeitnow returned an unexpected response format (expected a data array).")
        raw_jobs.extend(item for item in payload["data"] if isinstance(item, dict))
        links = payload.get("links")
        next_url = links.get("next") if isinstance(links, dict) else None
        if not next_url:
            break

    jobs = [normalize_job(item) for item in raw_jobs]
    _write_cache(jobs, timestamp)
    return jobs
