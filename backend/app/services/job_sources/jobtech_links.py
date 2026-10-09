import hashlib
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.job import JobPosting, WorkMode
from app.services.job_sources.base import JobSourceError

API_URL = "https://links.api.jobtechdev.se/joblinks"


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("name", "label", "value", "text"):
            if value.get(key) is not None:
                parsed = _text(value[key])
                if parsed:
                    return parsed
    return ""


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        parsed = _text(data.get(key))
        if parsed:
            return parsed
    return ""


def _get_company(ad: dict[str, Any]) -> str:
    employer = ad.get("employer")
    if isinstance(employer, dict):
        return _first_text(employer, "name", "workplace")
    return _text(employer)


def _address_dict(ad: dict[str, Any]) -> dict[str, Any]:
    address = ad.get("workplace_address")
    return address if isinstance(address, dict) else {}


def _get_city(ad: dict[str, Any]) -> str:
    address = _address_dict(ad)
    return _first_text(address, "municipality", "city", "municipality_name")


def _get_country(ad: dict[str, Any]) -> str:
    address = _address_dict(ad)
    return _first_text(address, "country", "country_name")


def _get_location(ad: dict[str, Any]) -> str:
    raw_address = ad.get("workplace_address")
    if isinstance(raw_address, str):
        return raw_address.strip()
    address = _address_dict(ad)

    parts: list[str] = []
    for key in ("municipality", "city", "region", "country"):
        value = _text(address.get(key))
        if value and value.casefold() not in {part.casefold() for part in parts}:
            parts.append(value)
    if parts:
        return ", ".join(parts)
    return _first_text(ad, "location", "municipality", "region")


def _safe_http_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return ""
    return value


def _get_source_url(ad: dict[str, Any]) -> str:
    links = ad.get("source_links", [])
    if isinstance(links, dict):
        links = [links]
    if not isinstance(links, list):
        return ""

    for link in links:
        if isinstance(link, str):
            url = _safe_http_url(link)
            if url:
                return url
        elif isinstance(link, dict):
            url = _safe_http_url(_first_text(link, "url", "href", "link"))
            if url:
                return url
    return _safe_http_url(_first_text(ad, "url", "webpage_url"))


def _classify_work_mode(ad: dict[str, Any]) -> WorkMode:
    """Classify only when structured metadata or text gives explicit evidence."""
    explicit_remote = ad.get("remote_work", ad.get("remote"))
    if explicit_remote is True:
        return "remote"

    structured = " ".join(
        _first_text(ad, key)
        for key in (
            "work_mode",
            "workplace_type",
            "workplace_type_label",
            "work_mode_label",
            "remote_work_type",
        )
    ).casefold()

    description = " ".join(
        _first_text(ad, key)
        for key in ("headline", "title", "brief", "description", "description_text")
    ).casefold()

    text = f"{structured} {description}"
    text = re.sub(r"\s+", " ", text)

    hybrid_patterns = (
        r"\bhybrid\b",
        r"\bdelvis distansarbete\b",
        r"\bkombinerat distansarbete\b",
        r"\bhybridarbete\b",
    )
    remote_patterns = (
        r"\bremote\b",
        r"\bfully remote\b",
        r"\bremote-first\b",
        r"\bwork from home\b",
        r"\bworking from home\b",
        r"\bdistansarbete\b",
        r"\barbeta på distans\b",
        r"\bkan arbeta på distans\b",
        r"\bhemifrån\b",
    )
    onsite_patterns = (
        r"\bon[- ]site\b",
        r"\bon site\b",
        r"\bin-office\b",
        r"\bpå plats\b",
        r"\bpå kontoret\b",
        r"\bfysiskt på kontor\b",
        r"\barbete på arbetsplatsen\b",
    )

    if any(re.search(pattern, text) for pattern in hybrid_patterns):
        return "hybrid"
    if any(re.search(pattern, text) for pattern in remote_patterns):
        return "remote"
    if any(re.search(pattern, text) for pattern in onsite_patterns):
        return "on_site"
    return "unknown"


def normalize_job(ad: dict[str, Any]) -> JobPosting:
    """Normalize one JobAd Links result into CareerMate's job schema."""
    source_id = _text(ad.get("id"))
    title = _first_text(ad, "headline", "title")
    company = _get_company(ad)
    location = _get_location(ad)
    source_url = _get_source_url(ad)

    if not source_id:
        identity = "|".join([title, company, location, source_url])
        source_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    return JobPosting(
        id=f"jobtech-links:{source_id}",
        source="jobtech_links",
        source_id=source_id,
        title=title or "Untitled position",
        company=company or "Company not specified",
        location=location or "Location not specified",
        description=_first_text(ad, "brief", "description", "description_text"),
        published_at=_first_text(ad, "publication_date", "published_at", "published"),
        source_url=source_url,
        apply_url=source_url,
        city=_get_city(ad),
        country=_get_country(ad),
        work_mode=_classify_work_mode(ad),
    )


def search_jobs(
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[JobPosting]]:
    """Search the official public JobAd Links API.

    This adapter uses the documented free-text query plus limit/offset.
    Other preferences are handled conservatively by the discovery layer
    where enough metadata is present; they are not presented as native
    API filters.
    """
    if not query.strip():
        raise JobSourceError("Enter a job title or keyword.")
    if not 1 <= limit <= 100:
        raise JobSourceError("Limit must be between 1 and 100.")
    if not 0 <= offset <= 2000:
        raise JobSourceError("Offset must be between 0 and 2000.")

    try:
        response = httpx.get(
            API_URL,
            params={"q": query.strip(), "limit": limit, "offset": offset},
            headers={"accept": "application/json", "user-agent": "CareerMate-local/0.1"},
            timeout=httpx.Timeout(20.0, connect=8.0),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise JobSourceError("The job source timed out. Please try again.") from exc
    except httpx.HTTPStatusError as exc:
        raise JobSourceError(
            f"Job source returned HTTP {exc.response.status_code}. Please try again later."
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise JobSourceError("Could not retrieve valid results from the job source.") from exc

    if not isinstance(payload, dict):
        raise JobSourceError("Unexpected response format from the job source.")

    raw_hits = payload.get("hits", [])
    total_data = payload.get("total", {})
    if not isinstance(raw_hits, list):
        raise JobSourceError("The job source returned an unexpected jobs format.")

    total_value = total_data.get("value", 0) if isinstance(total_data, dict) else total_data
    try:
        total = int(total_value or 0)
    except (TypeError, ValueError):
        total = len(raw_hits)

    jobs = [normalize_job(item) for item in raw_hits if isinstance(item, dict)]
    return total, jobs
