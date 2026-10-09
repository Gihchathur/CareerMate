from typing import Literal
from urllib.parse import urlparse, urlunparse

from app.models.job import JobPosting
from app.services.job_sources.base import JobSourceError
from app.services.job_sources.jobtech_links import search_jobs
from app.services.job_search import fetch_configured_jobs

WorkModePreference = Literal["any", "remote", "hybrid", "on_site"]


class JobDiscoveryError(Exception):
    """Raised when search preferences cannot be applied."""


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _dedupe_key(job: JobPosting) -> str:
    # Prefer the listing URL so a job mirrored by more than one source can be
    # deduplicated across providers, not just within a provider.
    url = job.source_url or job.apply_url
    if url:
        parsed = urlparse(url)
        normalized_url = urlunparse(parsed._replace(query="", fragment="")).rstrip("/")
        if normalized_url:
            return f"url:{normalized_url.casefold()}"

    if job.source and job.source_id:
        return f"source:{_normalize(job.source)}:{_normalize(job.source_id)}"

    title = _normalize(job.title)
    company = _normalize(job.company)
    location = _normalize(job.location)
    if title and company and company != "company not specified":
        return f"fallback:{title}|{company}|{location}"

    return job.id


def normalize_roles(roles: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_role in roles:
        for line in raw_role.splitlines():
            role = " ".join(line.strip().split())
            if not role:
                continue
            key = role.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(role)

    if not normalized:
        raise JobDiscoveryError("Enter at least one job title or keyword.")
    if len(normalized) > 5:
        raise JobDiscoveryError("Search up to five job titles at a time.")
    if any(len(role) > 100 for role in normalized):
        raise JobDiscoveryError("Each job title or keyword must be 100 characters or fewer.")

    return normalized


def _role_matches(role: str, job: JobPosting) -> bool:
    """Match a configured career-board result to a user's free-text role."""
    needle = _normalize(role)
    title = _normalize(job.title)
    full_text = _normalize(f"{job.title} {job.description}")
    if needle in title:
        return True
    tokens = [token for token in needle.split() if len(token) >= 3]
    if tokens and all(token in title for token in tokens):
        return True
    return needle in full_text or (len(tokens) >= 2 and all(token in full_text for token in tokens))


def _matches_sweden(job: JobPosting) -> bool:
    country = _normalize(job.country)
    location = _normalize(job.location)
    if country and country not in {"sweden", "sverige"}:
        return False
    # Reject known non-Swedish results even if the provider did not fill country.
    known_non_swedish = (
        "norway", "norge", "denmark", "danmark", "finland", "suomi",
        "germany", "deutschland", "united states", "united kingdom",
    )
    if any(marker in location for marker in known_non_swedish):
        return False
    if "sweden" in location or "sverige" in location:
        return True
    # When a board does not expose country data, keep the result as unknown
    # rather than silently discarding it. Users can tighten the city filter.
    return not country


def search_multiple_roles(
    *,
    roles: list[str],
    country: str,
    city: str,
    work_mode: WorkModePreference,
    limit: int,
    offset: int,
    sources: list[str] | None = None,
) -> dict[str, object]:
    """Search JobAd Links and enabled employer boards, then combine results.

    JobAd Links receives each role/city as free text. Greenhouse, Lever and
    Teamtailor require explicitly configured employer identifiers and are
    filtered locally because they do not provide one global job-search API.
    """
    cleaned_roles = normalize_roles(roles)
    allowed_sources = {"jobtech_links", "greenhouse", "lever", "teamtailor"}
    selected_sources = (
        ["jobtech_links", "greenhouse", "lever", "teamtailor"]
        if sources is None
        else list(dict.fromkeys(str(item).strip().casefold() for item in sources if str(item).strip()))
    )
    unknown_sources = sorted(set(selected_sources) - allowed_sources)
    if unknown_sources:
        raise JobDiscoveryError(f"Unsupported job source(s): {', '.join(unknown_sources)}.")
    if not selected_sources:
        raise JobDiscoveryError("Select at least one job source.")

    if country.strip().casefold() not in {"sweden", "sverige"}:
        raise JobDiscoveryError(
            "The currently connected job source is configured for Sweden. "
            "Additional country sources have not been connected yet."
        )
    if len(city) > 100:
        raise JobDiscoveryError("City must be 100 characters or fewer.")
    if not 1 <= limit <= 40:
        raise JobDiscoveryError("Page size must be between 1 and 40.")
    if not 0 <= offset <= 2000:
        raise JobDiscoveryError("Offset must be between 0 and 2000.")
    if work_mode not in {"any", "remote", "hybrid", "on_site"}:
        raise JobDiscoveryError("Unsupported work-mode preference.")

    page_by_role: list[list[JobPosting]] = []
    role_totals: list[int] = []
    has_more_by_role: list[bool] = []
    warnings: list[str] = []
    filter_rejected = 0
    successful_searches = 0

    selected_ats_sources = [source for source in selected_sources if source != "jobtech_links"]
    try:
        employer_jobs, employer_warnings, configured_boards = fetch_configured_jobs(selected_ats_sources)
    except JobSourceError as exc:
        employer_jobs, employer_warnings, configured_boards = [], [str(exc)], 0
    warnings.extend(employer_warnings)
    if configured_boards:
        successful_searches += max(0, configured_boards - len(employer_warnings))

    for role in cleaned_roles:
        query = " ".join(part.strip() for part in (role, city) if part.strip())
        if "jobtech_links" not in selected_sources:
            total, source_jobs = 0, []
        else:
            try:
                total, source_jobs = search_jobs(query=query, limit=limit, offset=offset)
                successful_searches += 1
            except JobSourceError as exc:
                warnings.append(f"{role}: {exc}")
                total, source_jobs = 0, []

        filtered_jobs: list[JobPosting] = []
        for job in source_jobs:
            # Persist the search role so users can tell which query found it.
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            if work_mode != "any" and job.work_mode != work_mode:
                filter_rejected += 1
                continue
            filtered_jobs.append(job)

        employer_matches = [
            job for job in employer_jobs
            if _role_matches(role, job)
            and (not city.strip() or _normalize(city) in _normalize(job.location))
            and _matches_sweden(job)
        ]
        employer_filtered: list[JobPosting] = []
        for job in employer_matches:
            if work_mode != "any" and job.work_mode != work_mode:
                filter_rejected += 1
                continue
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            employer_filtered.append(job)

        # Public career-board adapters fetch complete listings; apply the same
        # offset/page size locally after filtering so pages remain consistent.
        employer_page = employer_filtered[offset:offset + limit]
        filtered_jobs.extend(employer_page)
        role_totals.append(total + len(employer_matches))
        has_more_by_role.append(offset + len(source_jobs) < total or offset + limit < len(employer_filtered))
        page_by_role.append(filtered_jobs)

    if successful_searches == 0 and not employer_jobs and warnings:
        raise JobSourceError("All role searches failed. " + " | ".join(warnings))

    # Round-robin the query result sets to avoid allowing the first role to
    # consume the complete page before later roles are represented.
    combined: list[JobPosting] = []
    deduped: dict[str, JobPosting] = {}
    max_length = max((len(items) for items in page_by_role), default=0)

    for index in range(max_length):
        for role_jobs in page_by_role:
            if index >= len(role_jobs):
                continue
            job = role_jobs[index]
            key = _dedupe_key(job)

            if key in deduped:
                prior = deduped[key]
                merged_roles = list(dict.fromkeys(prior.search_roles + job.search_roles))
                updated = prior.model_copy(update={"search_roles": merged_roles})
                deduped[key] = updated
                # Replace already appended object as well.
                for position, existing in enumerate(combined):
                    if _dedupe_key(existing) == key:
                        combined[position] = updated
                        break
                continue

            deduped[key] = job
            combined.append(job)

    has_more = any(has_more_by_role)
    total_reported = sum(role_totals)
    total_is_approximate = (
        len(cleaned_roles) > 1
        or work_mode != "any"
        or configured_boards > 0
        or any(source != "jobtech_links" for source in selected_sources)
    )

    filter_note = ""
    if "jobtech_links" in selected_sources:
        filter_note += "JobAd Links receives role and city as free text, not as an exact structured location filter. "
    if selected_ats_sources:
        filter_note += (
            "Employer career boards are configured per company and their role, city, country, and work-mode "
            "preferences are applied locally where data is available. "
        )
    filter_note += (
        "Work mode is inferred from explicit metadata or listing text; choosing a specific mode excludes unknown results."
    )
    if total_is_approximate:
        filter_note += " Totals can be approximate because of cross-role duplicates and local filtering."

    return {
        "roles": cleaned_roles,
        "country": "Sweden",
        "city": city.strip(),
        "work_mode": work_mode,
        "total_reported": total_reported,
        "total_is_approximate": total_is_approximate,
        "offset": offset,
        "limit": limit,
        "returned": min(len(combined), limit),
        "has_more": has_more and offset < 2000,
        "filtered_out": filter_rejected,
        "role_searches": len(cleaned_roles),
        "sources": selected_sources,
        "configured_employer_boards": configured_boards,
        "warnings": warnings,
        "filter_note": filter_note,
        "jobs": combined[:limit],
    }
