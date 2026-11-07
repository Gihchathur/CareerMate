"""Adapter for Teamtailor's authenticated public-read API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    JobSourceIncompleteError,
    get_with_retries,
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
    page_size: int = 30,
    max_pages: int = 200,
) -> list[JobPosting]:
    """Fetch every publicly published job through Teamtailor's JSON:API pages."""
    if not api_key.strip():
        raise JobSourceError(f"Teamtailor API key is missing for '{company_name}'.")
    region_key = region.strip().casefold()
    if region_key not in API_ROOTS:
        raise JobSourceError("Teamtailor region must be 'eu', 'na', or 'apac'.")
    if not company_name.strip():
        raise JobSourceError("A Teamtailor company name is required.")
    # Teamtailor documents a maximum page[size] of 30. The previous code asked
    # for 100, then stopped as soon as the API silently returned a 30-row page.
    if not 1 <= page_size <= 30 or not 1 <= max_pages <= 500:
        raise JobSourceError("Teamtailor page size must be 1–30 and max_pages must be 1–500.")

    jobs: list[JobPosting] = []
    current_page = 1
    pages_fetched = 0
    next_url: str | None = None
    visited_next_urls: set[str] = set()
    for _page_index in range(max_pages):
        request_url = next_url or API_ROOTS[region_key]
        request_params = None if next_url else {
            "page[size]": page_size,
            "page[number]": current_page,
            "filter[status]": "published",
            "filter[feed]": "public",
            "include": "locations",
        }
        try:
            response = get_with_retries(
                request_url,
                params=request_params,
                headers={
                    "accept": "application/vnd.api+json",
                    "authorization": f"Token token={api_key.strip()}",
                    # Teamtailor documents using today's date to request its latest API version.
                    "x-api-version": datetime.now(timezone.utc).strftime("%Y%m%d"),
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

        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise JobSourceError(f"Teamtailor account '{company_name}' returned an unexpected response format (expected a data array).")
        data = [item for item in payload["data"] if isinstance(item, dict)]
        pages_fetched += 1
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
            location_names = [
                location_by_id[str(loc.get("id"))]
                for loc in loc_data
                if isinstance(loc, dict) and str(loc.get("id")) in location_by_id
            ] if isinstance(loc_data, list) else []
            jobs.append(normalize_job(
                {**item, "_careermate_locations": location_names},
                company_name=company_name,
                default_country=default_country,
            ))

        links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
        candidate_next = links.get("next")
        if candidate_next:
            # Follow provider-supplied cursors, but never send the API key to
            # an unexpected origin returned in a pagination payload.
            candidate_url = urljoin(request_url, str(candidate_next))
            parsed_next = urlparse(candidate_url)
            expected = urlparse(API_ROOTS[region_key])
            if parsed_next.scheme != "https" or parsed_next.netloc != expected.netloc or parsed_next.path != "/v1/jobs":
                raise JobSourceError("Teamtailor returned an unexpected pagination URL; the next page was not requested.")
            if candidate_url in visited_next_urls or candidate_url == request_url:
                fetched_at = datetime.now(timezone.utc).isoformat()
                partial_jobs = [job.model_copy(update={"source_fetched_at": fetched_at}) for job in jobs]
                raise JobSourceIncompleteError(
                    f"Teamtailor account '{company_name}' returned a repeated pagination cursor; results are partial.",
                    partial_jobs,
                )
            visited_next_urls.add(candidate_url)
            next_url = candidate_url
            continue

        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        try:
            page_count = int(meta.get("page-count", 0) or 0)
        except (TypeError, ValueError):
            page_count = 0
        if page_count and pages_fetched < page_count:
            current_page = pages_fetched + 1
            next_url = None
            continue
        if page_count and pages_fetched >= page_count:
            return jobs
        # Some compatible gateways omit links/meta. A full page is the only
        # safe fallback signal to try the following page.
        if len(data) >= page_size:
            current_page = pages_fetched + 1
            next_url = None
            continue
        return jobs

    fetched_at = datetime.now(timezone.utc).isoformat()
    partial_jobs = [job.model_copy(update={"source_fetched_at": fetched_at}) for job in jobs]
    raise JobSourceIncompleteError(
        f"Teamtailor account '{company_name}' reached the {max_pages * page_size:,}-job pagination safety limit; results are partial.",
        partial_jobs,
    )
