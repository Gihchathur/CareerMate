
import hashlib
from typing import Any

import httpx

from app.models.job import JobPosting


API_URL = "https://links.api.jobtechdev.se/joblinks"


class JobSourceError(Exception):
    """Raised when the job source cannot be queried."""


def _text(value: Any) -> str:
    """Convert common API values into readable text."""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, dict):
        for key in ("name", "label", "value", "text"):
            if value.get(key) is not None:
                return _text(value[key])

    return ""


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value

    return ""


def _get_company(ad: dict[str, Any]) -> str:
    employer = ad.get("employer")

    if isinstance(employer, dict):
        return _first_text(
            employer,
            "name",
            "workplace",
        )

    return _text(employer)


def _get_location(ad: dict[str, Any]) -> str:
    address = ad.get("workplace_address")

    if isinstance(address, str):
        return address.strip()

    if not isinstance(address, dict):
        address = {}

    parts = []

    for key in (
        "municipality",
        "city",
        "region",
        "country",
    ):
        value = _text(address.get(key))

        if value and value not in parts:
            parts.append(value)

    if parts:
        return ", ".join(parts)

    return _first_text(
        ad,
        "location",
        "municipality",
        "region",
    )


def _get_source_url(ad: dict[str, Any]) -> str:
    source_links = ad.get("source_links", [])

    if not isinstance(source_links, list):
        return ""

    for link in source_links:
        if not isinstance(link, dict):
            continue

        url = _first_text(link, "url", "href", "link")

        if url.startswith(("https://", "http://")):
            return url

    return ""


def normalize_job(ad: dict[str, Any]) -> JobPosting:
    """Convert one provider result to the CareerMate schema."""

    source_id = _text(ad.get("id"))

    title = _first_text(
        ad,
        "headline",
        "title",
    )

    company = _get_company(ad)
    location = _get_location(ad)

    source_url = _get_source_url(ad)

    # Use a stable fallback if the API record has no ID.
    if not source_id:
        identity = "|".join(
            [title, company, location, source_url]
        )

        source_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()[:24]

    return JobPosting(
        id=f"jobtech-links:{source_id}",
        source="jobtech_links",
        source_id=source_id,
        title=title or "Untitled position",
        company=company or "Company not specified",
        location=location or "Location not specified",
        description=_first_text(
            ad,
            "brief",
            "description",
        ),
        published_at=_first_text(
            ad,
            "publication_date",
            "published_at",
            "published",
        ),
        source_url=source_url,
        apply_url=source_url,
    )


def search_jobs(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[JobPosting]]:
    """Search the public JobAd Links API."""

    if not query.strip():
        raise JobSourceError("Enter a job title or keyword.")

    if not 1 <= limit <= 100:
        raise JobSourceError("Limit must be between 1 and 100.")

    if offset < 0:
        raise JobSourceError("Offset cannot be negative.")

    try:
        response = httpx.get(
            API_URL,
            params={
                "q": query.strip(),
                "limit": limit,
                "offset": offset,
            },
            headers={
                "accept": "application/json",
            },
            timeout=25.0,
        )

        response.raise_for_status()
        payload = response.json()

    except httpx.TimeoutException as exc:
        raise JobSourceError(
            "The job source timed out. Please try again."
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise JobSourceError(
            f"Job source returned HTTP {exc.response.status_code}."
        ) from exc

    except (httpx.RequestError, ValueError) as exc:
        raise JobSourceError(
            "Could not retrieve job listings from the API."
        ) from exc

    if not isinstance(payload, dict):
        raise JobSourceError("Unexpected response from job source.")

    raw_hits = payload.get("hits", [])
    total_data = payload.get("total", {})

    if not isinstance(raw_hits, list):
        raise JobSourceError("Unexpected job listing format.")

    total = (
        total_data.get("value", 0)
        if isinstance(total_data, dict)
        else total_data
    )

    jobs = [
        normalize_job(ad)
        for ad in raw_hits
        if isinstance(ad, dict)
    ]

    return int(total or 0), jobs
