"""Adapter for an employer's public Greenhouse Job Board API."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    get_with_retries,
    classify_work_mode,
    clean_html,
    infer_country,
    make_job_id,
    safe_http_url,
    text_value,
)

API_ROOT = "https://boards-api.greenhouse.io/v1/boards"


def normalize_job(
    raw: dict[str, Any],
    *,
    board_token: str,
    company_name: str = "",
    default_country: str = "",
) -> JobPosting:
    source_id = text_value(raw.get("id"))
    location_data = raw.get("location")
    location = text_value(location_data.get("name")) if isinstance(location_data, dict) else text_value(location_data)
    offices = raw.get("offices")
    if not location and isinstance(offices, list):
        location = ", ".join(
            text_value(item.get("location") or item.get("name"))
            for item in offices if isinstance(item, dict) and text_value(item.get("location") or item.get("name"))
        )
    title = text_value(raw.get("title")) or "Untitled position"
    description = clean_html(raw.get("content"))
    source_url = safe_http_url(raw.get("absolute_url"))
    if not source_id:
        source_id = source_url or f"{board_token}:{title}:{location}"
    company = text_value(raw.get("company_name")) or company_name.strip() or board_token
    country = infer_country(location, default_country)
    work_mode = classify_work_mode(raw.get("workplace_type"), raw.get("work_mode"), title, description)

    return JobPosting(
        id=make_job_id("greenhouse", f"{board_token}:{source_id}"),
        source="greenhouse",
        source_id=f"{board_token}:{source_id}",
        title=title,
        company=company,
        location=location or "Location not specified",
        description=description,
        published_at=text_value(raw.get("updated_at") or raw.get("first_published")),
        source_url=source_url,
        apply_url=source_url,
        city="",
        country=country,
        work_mode=work_mode,
    )


def fetch_board_jobs(
    board_token: str,
    *,
    company_name: str = "",
    default_country: str = "",
) -> list[JobPosting]:
    """Fetch all public jobs from one known Greenhouse board token."""
    token = board_token.strip()
    if not token or len(token) > 120:
        raise JobSourceError("A valid Greenhouse board token is required.")
    url = f"{API_ROOT}/{quote(token, safe='')}/jobs"
    try:
        response = get_with_retries(
            url,
            params={"content": "true"},
            headers={"accept": "application/json", "user-agent": "CareerMate-local/0.1"},
            timeout=httpx.Timeout(20.0, connect=8.0),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise JobSourceError(f"Greenhouse board '{token}' timed out.") from exc
    except httpx.HTTPStatusError as exc:
        raise JobSourceError(f"Greenhouse board '{token}' returned HTTP {exc.response.status_code}.") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise JobSourceError(f"Could not retrieve valid Greenhouse data for board '{token}'.") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise JobSourceError(f"Greenhouse board '{token}' returned an unexpected response format (expected a jobs array).")

    return [
        normalize_job(item, board_token=token, company_name=company_name, default_country=default_country)
        for item in payload.get("jobs", []) if isinstance(item, dict)
    ]
