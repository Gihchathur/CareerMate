"""Adapter for a company's public Lever Postings API."""

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

API_ROOTS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings",
}


def normalize_job(
    raw: dict[str, Any],
    *,
    site: str,
    company_name: str = "",
    default_country: str = "",
) -> JobPosting:
    source_id = text_value(raw.get("id")) or text_value(raw.get("hostedUrl"))
    categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    location = text_value(categories.get("location"))
    all_locations = categories.get("allLocations")
    if not location and isinstance(all_locations, list):
        location = ", ".join(text_value(item) for item in all_locations if text_value(item))
    title = text_value(raw.get("text")) or "Untitled position"
    description = text_value(raw.get("descriptionPlain")) or clean_html(raw.get("description"))
    source_url = safe_http_url(raw.get("hostedUrl"))
    apply_url = safe_http_url(raw.get("applyUrl")) or source_url
    workplace_type = text_value(raw.get("workplaceType"))
    if workplace_type == "on-site":
        work_mode = "on_site"
    elif workplace_type in {"remote", "hybrid"}:
        work_mode = workplace_type
    else:
        work_mode = classify_work_mode(workplace_type, title, description)
    country = infer_country(location, default_country)
    raw_country = text_value(raw.get("country")).upper()
    if not country and raw_country == "SE":
        country = "Sweden"
    elif not country and raw_country == "NO":
        country = "Norway"
    elif not country and raw_country == "DK":
        country = "Denmark"
    elif not country and raw_country == "FI":
        country = "Finland"
    elif not country and raw_country == "DE":
        country = "Germany"

    return JobPosting(
        id=make_job_id("lever", f"{site}:{source_id}"),
        source="lever",
        source_id=f"{site}:{source_id}",
        title=title,
        company=company_name.strip() or site,
        location=location or "Location not specified",
        description=description,
        published_at=text_value(raw.get("createdAt")),
        source_url=source_url,
        apply_url=apply_url,
        city="",
        country=country,
        work_mode=work_mode,  # type: ignore[arg-type]
    )


def fetch_site_jobs(
    site: str,
    *,
    company_name: str = "",
    region: str = "global",
    default_country: str = "",
    page_size: int = 100,
    max_pages: int = 10,
) -> list[JobPosting]:
    """Fetch published jobs from one known Lever site slug."""
    site_slug = site.strip()
    region_key = region.strip().casefold()
    if not site_slug or len(site_slug) > 120:
        raise JobSourceError("A valid Lever site slug is required.")
    if region_key not in API_ROOTS:
        raise JobSourceError("Lever region must be 'global' or 'eu'.")
    if not 1 <= page_size <= 100 or not 1 <= max_pages <= 20:
        raise JobSourceError("Invalid Lever pagination settings.")

    jobs: list[JobPosting] = []
    for page in range(max_pages):
        try:
            response = get_with_retries(
                f"{API_ROOTS[region_key]}/{quote(site_slug, safe='')}",
                params={"mode": "json", "skip": page * page_size, "limit": page_size},
                headers={"accept": "application/json", "user-agent": "CareerMate-local/0.1"},
                timeout=httpx.Timeout(20.0, connect=8.0),
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise JobSourceError(f"Lever site '{site_slug}' timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise JobSourceError(f"Lever site '{site_slug}' returned HTTP {exc.response.status_code}.") from exc
        except (httpx.RequestError, ValueError) as exc:
            raise JobSourceError(f"Could not retrieve valid Lever data for site '{site_slug}'.") from exc

        if not isinstance(payload, list):
            raise JobSourceError(f"Lever site '{site_slug}' returned an unexpected response format.")
        jobs.extend(
            normalize_job(item, site=site_slug, company_name=company_name, default_country=default_country)
            for item in payload if isinstance(item, dict)
        )
        if len(payload) < page_size:
            break
    return jobs
