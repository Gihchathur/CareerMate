"""Public employer ATS adapters with complete-board pagination and stale-cache safety.

CareerMate intentionally fetches the complete published inventory from each
selected employer board, then performs role/location filtering locally. Provider
search parameters are not used as the source of truth because their search
semantics and result limits differ between platforms.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import hashlib
import json
import os
import re
import time

import httpx

from app.models.job import JobPosting
from app.services.job_sources.base import (
    JobSourceError,
    JobSourceIncompleteError,
    JobSourceStaleCacheError,
    classify_work_mode,
    clean_html,
    get_with_retries,
    infer_country,
    make_job_id,
    safe_http_url,
    text_value,
)

UA = {
    "User-Agent": "CareerMate/3.8 (local employer career-board discovery; public ATS APIs)",
    "Accept": "application/json, application/xml, text/xml, */*",
}
CACHE_DIR = Path(__file__).resolve().parents[4] / "data" / "source_cache" / "public_ats"
DEFAULT_CACHE_TTL_SECONDS = 120
MAX_BOARD_JOBS = 10_000
PAGE_SIZE = 100


def _cache_ttl() -> int:
    try:
        return max(0, min(3600, int(os.getenv("CAREERMATE_PORTAL_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_CACHE_TTL_SECONDS


def _get(url: str, params=None):
    try:
        return get_with_retries(url, params=params, headers=UA, timeout=httpx.Timeout(25.0, connect=8.0))
    except Exception as exc:
        raise JobSourceError(f"Public board request failed: {exc}") from exc


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    response = _get(url, params)
    try:
        return response.json()
    except (ValueError, TypeError) as exc:
        raise JobSourceError(f"Public board returned invalid JSON: {url}") from exc


def _post_json(url: str, payload: dict[str, Any]):
    try:
        response = httpx.post(url, json=payload, headers=UA, timeout=httpx.Timeout(25.0, connect=8.0))
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        raise JobSourceError(f"Public board request failed: {exc}") from exc


def _postal_address(raw: dict[str, Any]) -> dict[str, Any]:
    address = raw.get("address") if isinstance(raw.get("address"), dict) else {}
    postal = address.get("postalAddress") if isinstance(address.get("postalAddress"), dict) else address
    return postal if isinstance(postal, dict) else {}


_COUNTRY_CODES = {
    "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "DE": "Germany", "NL": "Netherlands", "GB": "United Kingdom", "UK": "United Kingdom",
    "US": "United States", "USA": "United States", "U.S.A.": "United States",
    "CA": "Canada", "IE": "Ireland", "FR": "France",
    "ES": "Spain", "IT": "Italy", "PL": "Poland", "CH": "Switzerland",
    "AT": "Austria", "PT": "Portugal", "BE": "Belgium", "IS": "Iceland",
    "AU": "Australia", "NZ": "New Zealand", "IN": "India", "SG": "Singapore",
    "JP": "Japan", "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania",
    "CZ": "Czechia", "SK": "Slovakia", "HU": "Hungary", "RO": "Romania",
    "BG": "Bulgaria", "GR": "Greece", "HR": "Croatia", "SI": "Slovenia",
    "CY": "Cyprus", "LU": "Luxembourg", "MT": "Malta", "UA": "Ukraine",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CL": "Chile",
    "ZA": "South Africa", "AE": "United Arab Emirates", "IL": "Israel",
    "TR": "Türkiye", "KR": "South Korea", "CN": "China", "TW": "Taiwan",
    "TH": "Thailand", "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines",
    "VN": "Vietnam", "PK": "Pakistan", "BD": "Bangladesh", "NG": "Nigeria",
    "KE": "Kenya", "EG": "Egypt", "SA": "Saudi Arabia", "QA": "Qatar",
}


def _canonical_country(value: str, location: str, fallback: str) -> str:
    cleaned = value.strip()
    if cleaned:
        return _COUNTRY_CODES.get(cleaned.upper(), cleaned)
    return infer_country(location, fallback)


def _posting(
    source: str,
    sid: Any,
    title: Any,
    company: str,
    location: Any,
    description: Any,
    published: Any,
    url: Any,
    country: str = "",
    *,
    portal_slug: str = "",
    city: str = "",
    country_override: str = "",
    department: str = "",
    team: str = "",
    employment_type: str = "",
    role_metadata: list[str] | None = None,
    work_mode: str = "unknown",
) -> JobPosting:
    location_label = text_value(location) or "Location not specified"
    board_identity = portal_slug.strip().casefold()
    provider_job_id = text_value(sid) or f"{title}:{location_label}"
    stable_source_id = f"{board_identity}:{provider_job_id}" if board_identity else provider_job_id
    resolved_country = _canonical_country(country_override, location_label, country)
    detected_work_mode = work_mode if work_mode in {"remote", "hybrid", "on_site", "unknown"} else "unknown"
    if detected_work_mode == "unknown":
        detected_work_mode = classify_work_mode(location_label, description)

    return JobPosting(
        id=make_job_id(source, stable_source_id),
        source=source,
        source_id=stable_source_id,
        portal_id=f"{source}:{board_identity}" if board_identity else "",
        portal_name=company or portal_slug,
        title=text_value(title) or "Untitled role",
        company=company or "Company not specified",
        location=location_label,
        description=clean_html(text_value(description)),
        published_at=text_value(published),
        source_url=safe_http_url(url),
        apply_url=safe_http_url(url),
        city=city.strip(),
        country=resolved_country,
        work_mode=detected_work_mode,  # type: ignore[arg-type]
        department=department.strip(),
        team=team.strip(),
        employment_type=employment_type.strip(),
        role_metadata=[item.strip() for item in (role_metadata or []) if item and item.strip()],
    )


def _fetch_public_board_uncached(source: str, board: dict[str, Any]) -> list[JobPosting]:
    slug = str(board.get("slug", "")).strip()
    company = str(board.get("company", "")).strip() or slug
    country = str(board.get("country", "")).strip()
    if not slug:
        raise JobSourceError("Board slug is required.")

    jobs: list[JobPosting] = []

    if source == "ashby":
        # Ashby's public job-board endpoint returns the currently published
        # inventory in one response; do not apply a search term or page-size cap.
        payload = _get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
            {"includeCompensation": "true"},
        )
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise JobSourceError("Ashby returned an unexpected response format (expected a jobs array).")
        for item in rows:
            if not isinstance(item, dict) or item.get("isListed") is False:
                continue
            postal = _postal_address(item)
            location = text_value(item.get("location"))
            city = text_value(postal.get("addressLocality"))
            explicit_country = text_value(postal.get("addressCountry"))
            secondary = item.get("secondaryLocations")
            secondary_names = [
                text_value(entry.get("location")) if isinstance(entry, dict) else text_value(entry)
                for entry in secondary if isinstance(entry, (dict, str))
            ] if isinstance(secondary, list) else []
            location_parts = list(dict.fromkeys(part for part in [location, *secondary_names] if part))
            department = text_value(item.get("department"))
            team = text_value(item.get("team"))
            workplace_type = text_value(item.get("workplaceType")).casefold()
            workplace_mode = {
                "onsite": "on_site", "on-site": "on_site", "on site": "on_site",
                "remote": "remote", "hybrid": "hybrid",
            }.get(workplace_type, "unknown")
            # Ashby's isRemote is true for both Remote and Hybrid. Never infer
            # remote-only from that boolean when workplaceType is available.
            jobs.append(_posting(
                source,
                item.get("id"),
                item.get("title"),
                company,
                ", ".join(location_parts),
                item.get("descriptionPlain") or item.get("descriptionHtml") or item.get("description"),
                item.get("publishedAt"),
                item.get("jobUrl") or item.get("applyUrl"),
                country,
                portal_slug=slug,
                city=city,
                country_override=explicit_country,
                department=department,
                team=team,
                employment_type=text_value(item.get("employmentType")),
                role_metadata=[department, team],
                work_mode=workplace_mode,
            ))

    elif source == "smartrecruiters":
        # SmartRecruiters publishes totalFound; keep requesting pages until the
        # reported total is reached, rather than stopping after the first 500.
        offset = 0
        total_found: int | None = None
        while offset < MAX_BOARD_JOBS:
            payload = _get_json(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                {"limit": PAGE_SIZE, "offset": offset},
            )
            if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
                raise JobSourceError("SmartRecruiters returned an unexpected response format (expected a content array).")
            rows = [row for row in payload["content"] if isinstance(row, dict)]
            reported = payload.get("totalFound")
            if isinstance(reported, (int, float)):
                total_found = max(0, int(reported))
            for item in rows:
                loc = item.get("location") if isinstance(item.get("location"), dict) else {}
                location = loc.get("fullLocation") or ", ".join(
                    value for value in (text_value(loc.get("city")), text_value(loc.get("region")), text_value(loc.get("country"))) if value
                )
                jobs.append(_posting(
                    source, item.get("id"), item.get("name"), company, location,
                    item.get("jobAd") or item.get("description"), item.get("releasedDate"),
                    item.get("ref") or f"https://jobs.smartrecruiters.com/{slug}/{item.get('id')}",
                    country, portal_slug=slug, city=text_value(loc.get("city")),
                    country_override=text_value(loc.get("country")),
                    department=text_value(item.get("department", {}).get("label")) if isinstance(item.get("department"), dict) else text_value(item.get("department")),
                ))
            if not rows or len(rows) < PAGE_SIZE or (total_found is not None and offset + len(rows) >= total_found):
                break
            offset += len(rows)
        else:
            fetched_at = datetime.now(timezone.utc).isoformat()
            partial_jobs = [job.model_copy(update={"source_fetched_at": fetched_at}) for job in jobs]
            raise JobSourceIncompleteError(
                f"SmartRecruiters board '{company}' reached the {MAX_BOARD_JOBS:,}-job safety limit; results are partial.",
                partial_jobs,
            )

    elif source == "workable":
        payload = _get_json(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", {"details": "true"})
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise JobSourceError("Workable returned an unexpected response format (expected a jobs array).")
        for item in rows:
            if not isinstance(item, dict):
                continue
            location = ", ".join(value for value in (text_value(item.get("city")), text_value(item.get("state")), text_value(item.get("country"))) if value) or text_value(item.get("locations"))
            jobs.append(_posting(
                source, item.get("shortcode"), item.get("title"), company, location,
                item.get("description"), item.get("published_on"), item.get("application_url") or item.get("url"),
                country, portal_slug=slug, city=text_value(item.get("city")),
                country_override=text_value(item.get("country")),
                department=text_value(item.get("department")),
            ))

    elif source == "recruitee":
        payload = _get_json(f"https://{slug}.recruitee.com/api/offers/")
        rows = payload.get("offers") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise JobSourceError("Recruitee returned an unexpected response format (expected an offers array).")
        for item in rows:
            if not isinstance(item, dict):
                continue
            location = ", ".join(value for value in (text_value(item.get("city")), text_value(item.get("country_code"))) if value) or text_value(item.get("location"))
            description = " ".join(str(item.get(key, "")) for key in ("description", "requirements"))
            jobs.append(_posting(
                source, item.get("id"), item.get("title"), company, location, description,
                item.get("published_at"), item.get("careers_url") or item.get("careers_apply_url"),
                country, portal_slug=slug, city=text_value(item.get("city")),
                country_override=text_value(item.get("country")),
            ))

    elif source == "breezy":
        payload = _get_json(f"https://{slug}.breezy.hr/json")
        if not isinstance(payload, list):
            raise JobSourceError("Breezy returned an unexpected response format (expected a jobs array).")
        for item in payload:
            if not isinstance(item, dict):
                continue
            loc = item.get("location") if isinstance(item.get("location"), dict) else {}
            location = ", ".join(value for value in (text_value(loc.get("city")), text_value(loc.get("state")), text_value(loc.get("country"))) if value) or ("Remote" if loc.get("is_remote") else "")
            jobs.append(_posting(
                source, item.get("id"), item.get("name"), company, location, item.get("description"),
                item.get("published_date"), item.get("url"), country, portal_slug=slug,
                city=text_value(loc.get("city")), country_override=text_value(loc.get("country")),
                work_mode="remote" if loc.get("is_remote") else "unknown",
            ))

    elif source == "workday":
        board_url = slug
        parsed = urlparse(board_url if "://" in board_url else "https://" + board_url)
        match = re.fullmatch(r"(?P<tenant>[a-z0-9-]+)\.(?P<cluster>wd\d+)\.myworkdayjobs\.com", parsed.netloc, re.I)
        site_parts = [part for part in parsed.path.strip("/").split("/") if part]
        site = site_parts[-1] if site_parts else ""
        if not match or not site:
            raise JobSourceError("Workday board URL must include its tenant, wd cluster and public site path.")
        tenant = match.group("tenant")
        endpoint = f"https://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
        page_size = 20  # Workday CXS commonly caps this endpoint at 20 per request.
        offset = 0
        total_count: int | None = None
        while offset < MAX_BOARD_JOBS:
            payload = _post_json(endpoint, {"limit": page_size, "offset": offset, "searchText": "", "appliedFacets": {}})
            rows = payload.get("jobPostings") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise JobSourceError("Workday returned an unexpected response format (expected a jobPostings array).")
            reported = payload.get("total") or payload.get("totalCount") or payload.get("totalFound")
            if isinstance(reported, (int, float)):
                total_count = max(0, int(reported))
            for item in rows:
                if not isinstance(item, dict):
                    continue
                external_path = str(item.get("externalPath", ""))
                url = f"https://{parsed.netloc}/{site}{external_path}" if external_path else board_url
                location = text_value(item.get("locationsText")) or text_value(item.get("location"))
                jobs.append(_posting(
                    source, item.get("jobReqId") or external_path, item.get("title"), company,
                    location, item.get("bulletFields") or item.get("jobDescription"), item.get("postedOn"),
                    url, country, portal_slug=parsed.netloc.casefold() + ":" + site.casefold(),
                ))
            if not rows or len(rows) < page_size or (total_count is not None and offset + len(rows) >= total_count):
                break
            offset += len(rows)
        else:
            fetched_at = datetime.now(timezone.utc).isoformat()
            partial_jobs = [job.model_copy(update={"source_fetched_at": fetched_at}) for job in jobs]
            raise JobSourceIncompleteError(
                f"Workday board '{company}' reached the {MAX_BOARD_JOBS:,}-job safety limit; results are partial.",
                partial_jobs,
            )

    elif source == "personio":
        response = _get(f"https://{slug}.jobs.personio.de/xml", {"language": "en"})
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise JobSourceError("Personio returned invalid XML.") from exc
        for item in root.findall(".//position"):
            ident = item.findtext("id") or item.findtext("name") or slug
            title = item.findtext("name") or "Untitled role"
            location = item.findtext("office") or country
            descriptions = [description.findtext("value") or "" for description in item.findall(".//jobDescription")]
            url = item.findtext("jobUrl") or f"https://{slug}.jobs.personio.de/job/{ident}"
            jobs.append(_posting(
                source, ident, title, company, location, " ".join(descriptions),
                item.findtext("createdAt"), url, country, portal_slug=slug,
            ))

    else:
        raise JobSourceError(f"Unsupported public ATS source: {source}")

    fetched_at = datetime.now(timezone.utc).isoformat()
    return [job.model_copy(update={"source_fetched_at": fetched_at}) for job in jobs]


def _read_cache(cache_path: Path) -> tuple[list[JobPosting], datetime | None]:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):  # Backward compatibility with CareerMate 3.7 caches.
            fetched_at = datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc)
            jobs = []
            for item in payload:
                job = JobPosting.model_validate(item)
                jobs.append(job if job.source_fetched_at else job.model_copy(update={"source_fetched_at": fetched_at.isoformat()}))
            return jobs, fetched_at
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            fetched_at = datetime.fromisoformat(str(payload.get("fetched_at", "")).replace("Z", "+00:00"))
            jobs = []
            for item in payload["jobs"]:
                job = JobPosting.model_validate(item)
                jobs.append(job if job.source_fetched_at else job.model_copy(update={"source_fetched_at": fetched_at.isoformat()}))
            return jobs, fetched_at
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return [], None


def fetch_public_board(source: str, board: dict[str, Any], *, force_refresh: bool = False) -> list[JobPosting]:
    """Fetch all board jobs, use a short cache, and retain stale data on outages.

    Public career boards usually don't provide an uptime guarantee. A short cache
    avoids hitting every employer API on each pagination click, while stale-if-error
    prevents a temporary outage from making a known company appear to have zero jobs.
    """
    cache_identity = {"source": source, "board": board}
    cache_key = hashlib.sha256(json.dumps(cache_identity, sort_keys=True).encode()).hexdigest()
    cache_path = CACHE_DIR / f"{source}-{cache_key}.json"
    cached_jobs, fetched_at = _read_cache(cache_path)
    ttl = _cache_ttl()
    cache_age = (datetime.now(timezone.utc) - fetched_at).total_seconds() if fetched_at else None
    if cached_jobs and not force_refresh and ttl > 0 and cache_age is not None and cache_age <= ttl:
        return cached_jobs

    try:
        jobs = _fetch_public_board_uncached(source, board)
    except JobSourceError as exc:
        if cached_jobs:
            age_text = f"{int(cache_age // 60)} min old" if cache_age is not None else "previously saved"
            raise JobSourceStaleCacheError(
                f"Live refresh failed; showing the last successful {age_text} snapshot. {exc}",
                cached_jobs,
            ) from exc
        raise

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "jobs": [job.model_dump() for job in jobs],
        }, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
    except OSError:
        # Cache failure must not discard a successful live snapshot.
        pass
    return jobs
