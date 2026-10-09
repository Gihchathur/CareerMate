"""Adapter for Teamtailor's authenticated public-read API."""

from __future__ import annotations

from typing import Any

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    classify_work_mode,
    clean_html,
    infer_country,
    make_job_id,
    safe_http_url,
    text_value,
)

API_ROOTS = {
    "eu": "https://api.teamtailor.com/v1/jobs",
    "na": "https://api.na.teamtailor.com/v1/jobs",
    "apac": "https://api.au.teamtailor.com/v1/jobs",
}


def normalize_job(
    raw: dict[str, Any],
    *,
    company_name: str,
    default_country: str = "",
) -> JobPosting:
    source_id = text_value(raw.get("id")) or "unknown"
    attrs = raw.get("attributes") if isinstance(raw.get("attributes"), dict) else {}
    links = raw.get("links") if isinstance(raw.get("links"), dict) else {}
    title = text_value(attrs.get("title")) or "Untitled position"
    location = text_value(attrs.get("location"))
    locations = raw.get("_careermate_locations")
    if isinstance(locations, list) and locations:
        location = ", ".join(text_value(item) for item in locations if text_value(item))
    body = clean_html(attrs.get("body"))
    pitch = clean_html(attrs.get("pitch"))
    description = " ".join(part for part in (pitch, body) if part)
    source_url = safe_http_url(links.get("careersite-job-url"))
    apply_url = safe_http_url(links.get("careersite-job-apply-url")) or source_url
    remote_status = text_value(attrs.get("remote-status"))
    remote_map = {"fully": "remote", "hybrid": "hybrid", "temporary": "unknown", "none": "unknown"}
    work_mode = remote_map.get(remote_status, classify_work_mode(remote_status, title, description))
    country = infer_country(location, default_country)

    return JobPosting(
        id=make_job_id("teamtailor", f"{company_name}:{source_id}"),
        source="teamtailor",
        source_id=f"{company_name}:{source_id}",
        title=title,
        company=company_name.strip() or "Company not specified",
        location=location or "Location not specified",
        description=description,
        published_at=text_value(attrs.get("updated-at") or attrs.get("created-at")),
        source_url=source_url,
        apply_url=apply_url,
        city="",
        country=country,
        work_mode=work_mode,  # type: ignore[arg-type]
    )


def fetch_company_jobs(
    *,
    api_key: str,
    company_name: str,
    region: str = "eu",
    default_country: str = "",
    page_size: int = 100,
    max_pages: int = 10,
) -> list[JobPosting]:
    """Fetch public published jobs for a company account using a read-only API key."""
    if not api_key.strip():
        raise JobSourceError(f"Teamtailor API key is missing for '{company_name}'.")
    region_key = region.strip().casefold()
    if region_key not in API_ROOTS:
        raise JobSourceError("Teamtailor region must be 'eu', 'na', or 'apac'.")
    if not company_name.strip():
        raise JobSourceError("A Teamtailor company name is required.")
    if not 1 <= page_size <= 100 or not 1 <= max_pages <= 20:
        raise JobSourceError("Invalid Teamtailor pagination settings.")

    jobs: list[JobPosting] = []
    for page in range(1, max_pages + 1):
        try:
            response = httpx.get(
                API_ROOTS[region_key],
                params={
                    "page[size]": page_size,
                    "page[number]": page,
                    "filter[status]": "published",
                    "filter[feed]": "public",
                    "include": "locations",
                },
                headers={
                    "accept": "application/vnd.api+json",
                    "authorization": f"Token token={api_key.strip()}",
                    "x-api-version": "20240404",
                    "user-agent": "CareerMate-local/0.1",
                },
                timeout=httpx.Timeout(20.0, connect=8.0),
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            raise JobSourceError(f"Teamtailor account '{company_name}' timed out.") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = "Check the API key and its Public Read permission." if status in {401, 403} else ""
            raise JobSourceError(f"Teamtailor account '{company_name}' returned HTTP {status}. {detail}".strip()) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise JobSourceError(f"Could not retrieve valid Teamtailor data for '{company_name}'.") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("data", []), list):
            raise JobSourceError(f"Teamtailor account '{company_name}' returned an unexpected response format.")
        data = [item for item in payload.get("data", []) if isinstance(item, dict)]
        included = payload.get("included", [])
        location_by_id: dict[str, str] = {}
        if isinstance(included, list):
            for item in included:
                if not isinstance(item, dict) or item.get("type") != "locations":
                    continue
                attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
                location_name = text_value(attrs.get("name"))
                if item.get("id") is not None and location_name:
                    location_by_id[str(item["id"])] = location_name
        for item in data:
            relationships = item.get("relationships") if isinstance(item.get("relationships"), dict) else {}
            loc_rel = relationships.get("locations") if isinstance(relationships.get("locations"), dict) else {}
            loc_data = loc_rel.get("data", [])
            location_names = [location_by_id[str(loc.get("id"))] for loc in loc_data if isinstance(loc, dict) and str(loc.get("id")) in location_by_id] if isinstance(loc_data, list) else []
            jobs.append(normalize_job({**item, "_careermate_locations": location_names}, company_name=company_name, default_country=default_country))
        if len(data) < page_size:
            break
    return jobs
