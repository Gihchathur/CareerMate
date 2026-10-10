"""Adapter for Remote OK's public remote-jobs JSON feed.

Remote OK asks clients to credit the source and link to every original job.
CareerMate preserves those links and labels the source in the UI.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    clean_html,
    get_with_retries,
    infer_country,
    make_job_id,
    safe_http_url,
    text_value,
)

API_URL = "https://remoteok.com/api"
CACHE_PATH = Path(__file__).resolve().parents[4] / "data" / "source_cache" / "remoteok.json"
CACHE_TTL_SECONDS = 60 * 60
logger = logging.getLogger(__name__)


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
    temporary_path = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(
            json.dumps({"fetched_at": now, "jobs": [job.model_dump() for job in jobs]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(CACHE_PATH)
    except OSError:
        logger.warning("Could not write the local Remote OK cache", exc_info=True)
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def normalize_job(raw: dict[str, Any]) -> JobPosting:
    source_id = text_value(raw.get("id"))
    title = text_value(raw.get("position")) or text_value(raw.get("title")) or "Untitled position"
    company = text_value(raw.get("company")) or "Company not specified"
    location = text_value(raw.get("location")) or text_value(raw.get("region")) or "Remote"
    source_url = safe_http_url(raw.get("url"))
    apply_url = safe_http_url(raw.get("apply_url")) or source_url
    description = text_value(raw.get("description_plain")) or clean_html(raw.get("description"))
    tags = raw.get("tags")
    if isinstance(tags, list):
        tag_text = ", ".join(text_value(item) for item in tags if text_value(item))
        if tag_text:
            description = f"Tags: {tag_text}\n\n{description}".strip()
    if not source_id:
        source_id = source_url or f"{company}:{title}:{location}"

    country = infer_country(location, "")
    folded_location = location.casefold()
    if any(marker in folded_location for marker in ("worldwide", "anywhere", "global", "everywhere")):
        country = "Worldwide"

    return JobPosting(
        id=make_job_id("remoteok", source_id),
        source="remoteok",
        source_id=source_id,
        title=title,
        company=company,
        location=location,
        description=description[:30000],
        published_at=text_value(raw.get("date")) or text_value(raw.get("epoch")),
        source_url=source_url,
        apply_url=apply_url,
        city="",
        country=country,
        work_mode="remote",
    )


def fetch_remote_jobs(*, now: float | None = None, force_refresh: bool = False) -> list[JobPosting]:
    """Fetch and normalize the public feed, using a one-hour local cache."""
    timestamp = time.time() if now is None else now
    if not force_refresh:
        cached_jobs = _load_fresh_cache(timestamp)
        if cached_jobs is not None:
            return cached_jobs

    try:
        response = get_with_retries(
            API_URL,
            headers={
                "accept": "application/json",
                "user-agent": "CareerMate-local/0.1 (local personal job search)",
            },
            timeout=httpx.Timeout(20.0, connect=8.0),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise JobSourceError("Remote OK timed out. Please try again.") from exc
    except httpx.HTTPStatusError as exc:
        raise JobSourceError(f"Remote OK returned HTTP {exc.response.status_code}.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise JobSourceError("Could not retrieve valid data from Remote OK.") from exc

    if not isinstance(payload, list):
        raise JobSourceError("Remote OK returned an unexpected response format.")

    # The feed may start with an informational/legal object rather than a job.
    jobs = [
        normalize_job(item)
        for item in payload
        if isinstance(item, dict) and (text_value(item.get("id")) or text_value(item.get("url")))
        and (text_value(item.get("position")) or text_value(item.get("title")))
    ]
    _write_cache(jobs, timestamp)
    return jobs
