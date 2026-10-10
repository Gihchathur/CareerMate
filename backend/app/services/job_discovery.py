"""Multi-source job discovery with explicit country/source limitations."""

from typing import Literal
from urllib.parse import urlparse, urlunparse

from app.models.job import JobPosting
from app.services.job_sources.base import JobSourceError
from app.services.job_sources.arbeitnow import fetch_jobs as fetch_arbeitnow_jobs
from app.services.job_sources.jobtech_links import search_jobs
from app.services.job_sources.remoteok import fetch_remote_jobs
from app.services.job_search import fetch_configured_jobs

WorkModePreference = Literal["any", "remote", "hybrid", "on_site"]


class JobDiscoveryError(Exception):
    """Raised when search preferences cannot be applied."""


COUNTRY_ANY = "any country"
SUPPORTED_COUNTRIES = {
    "sweden", "sverige", "norway", "denmark", "finland", "germany", "netherlands",
    "united kingdom", "united states", "canada", "france", "switzerland", COUNTRY_ANY,
}
ARBEITNOW_COUNTRIES = {"germany", "united kingdom", "france", "switzerland"}


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _dedupe_key(job: JobPosting) -> str:
    # Prefer listing URL so a mirrored listing can be deduplicated across providers.
    url = job.source_url or job.apply_url
    if url:
        parsed = urlparse(url)
        normalized_url = urlunparse(parsed._replace(query="", fragment="")).rstrip("/")
        if normalized_url:
            return f"url:{normalized_url.casefold()}"
    if job.source and job.source_id:
        return f"source:{_normalize(job.source)}:{_normalize(job.source_id)}"
    title, company, location = _normalize(job.title), _normalize(job.company), _normalize(job.location)
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
    """Match a career-board result to a free-text role conservatively."""
    needle = _normalize(role)
    title = _normalize(job.title)
    full_text = _normalize(f"{job.title} {job.description}")
    if needle in title:
        return True
    tokens = [token for token in needle.split() if len(token) >= 3]
    if tokens and all(token in title for token in tokens):
        return True
    return needle in full_text or (len(tokens) >= 2 and all(token in full_text for token in tokens))


def _is_any_country(country: str) -> bool:
    return _normalize(country) in {COUNTRY_ANY, "any", "all countries", "worldwide"}


def _matches_country(job: JobPosting, selected_country: str) -> bool:
    """Apply a best-effort country filter; preserve unknown results but reject known mismatches."""
    if _is_any_country(selected_country):
        return True
    target = _normalize(selected_country)
    actual = _normalize(job.country)
    location = _normalize(job.location)
    if actual in {"worldwide", "global", "anywhere"} or any(
        marker in location for marker in ("worldwide", "anywhere", "global", "everywhere")
    ):
        return True
    if actual:
        return actual == target
    # Public job feeds often omit structured country. Use clear country text where available.
    known = (
        "sweden", "sverige", "norway", "norge", "denmark", "danmark", "finland", "suomi",
        "germany", "deutschland", "netherlands", "united kingdom", "united states", "usa",
        "canada", "ireland", "france", "spain", "italy", "poland", "estonia", "switzerland",
        "austria", "portugal", "belgium", "iceland", "australia", "new zealand", "india", "singapore",
    )
    for marker in known:
        if marker in location and marker not in target:
            return False
    if target == "sweden" and any(marker in location for marker in ("sweden", "sverige")):
        return True
    if target == "norway" and any(marker in location for marker in ("norway", "norge")):
        return True
    if target == "denmark" and any(marker in location for marker in ("denmark", "danmark")):
        return True
    if target == "finland" and any(marker in location for marker in ("finland", "suomi")):
        return True
    if target == "germany" and any(marker in location for marker in ("germany", "deutschland")):
        return True
    if target == "netherlands" and any(marker in location for marker in ("netherlands", "holland", "dutch")):
        return True
    if target == "united kingdom" and any(marker in location for marker in ("united kingdom", "uk only", "britain", "england", "scotland", "wales")):
        return True
    if target == "united states" and any(marker in location for marker in ("united states", "usa", "us only", "u.s.")):
        return True
    if target == "canada" and "canada" in location:
        return True
    # Unknown location/country metadata isn't enough to confidently reject a result.
    return True


_UNKNOWN_LOCATION_LABELS = {
    "", "unknown", "not specified", "location not specified", "location unknown",
    "n/a", "na", "remote", "remote only", "flexible", "various locations",
    "multiple locations",
}
_COUNTRY_ONLY_LOCATION_LABELS = {
    "sweden", "sverige", "norway", "norge", "denmark", "danmark", "finland",
    "suomi", "germany", "deutschland", "netherlands", "the netherlands", "holland",
    "united kingdom", "uk", "great britain", "britain", "united states", "usa", "us",
    "canada", "ireland", "france", "spain", "italy", "poland", "estonia", "switzerland",
    "austria", "portugal", "belgium", "iceland", "australia", "new zealand", "india",
    "singapore", "europe", "emea", "worldwide", "global", "anywhere", "everywhere",
}


def _matches_city(job: JobPosting, city: str, selected_country: str = "") -> bool:
    """Apply a best-effort city filter without discarding weakly-localized results.

    Public feeds sometimes return matching records without structured city data.
    Missing location metadata is unknown, not proof of a city mismatch. A populated
    structured city that names another city remains a firm mismatch. JobTech is
    queried with the requested city as free text, so its incomplete location records
    should not all disappear during a second local city filter.
    """
    target = _normalize(city)
    if not target:
        return True

    city_value = _normalize(job.city)
    location_value = _normalize(job.location)
    combined_location = _normalize(f"{job.city} {job.location}")
    if target in combined_location:
        return True

    if job.work_mode == "remote":
        if any(marker in combined_location for marker in ("worldwide", "anywhere", "global", "everywhere")):
            return True
        if selected_country and not _is_any_country(selected_country):
            if _normalize(job.country) == _normalize(selected_country):
                return True
            if any(marker in combined_location for marker in ("europe", "emea", "european union", "eu-wide")) and _normalize(selected_country) in {
                "sweden", "norway", "denmark", "finland", "germany", "netherlands", "united kingdom",
            }:
                return True
        # Remote feeds sometimes provide no region/country at all. Keep those
        # candidates visible rather than silently producing an empty result set.
        if location_value in _UNKNOWN_LOCATION_LABELS:
            return True

    # If the board provides a real city, it is reliable enough to filter on.
    if city_value and city_value not in _UNKNOWN_LOCATION_LABELS:
        return False

    # Missing/generic location metadata is not a confirmed mismatch. This is
    # especially important for JobTech because the selected city is already part
    # of its free-text request, while its response can omit the address components.
    if location_value in _UNKNOWN_LOCATION_LABELS:
        return True
    if job.source == "jobtech_links" and location_value in _COUNTRY_ONLY_LOCATION_LABELS:
        return True

    # For non-remote postings with a concrete location but no structured city field,
    # stay conservative. The target city's name would have matched above if present.
    return False


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
    """Search local configured boards plus public feeds and combine normalized listings."""
    cleaned_roles = normalize_roles(roles)
    allowed_sources = {"jobtech_links", "greenhouse", "lever", "teamtailor", "remoteok", "arbeitnow"}
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
    if _normalize(country) not in SUPPORTED_COUNTRIES:
        raise JobDiscoveryError(
            "Choose a supported country, or select Any country. Global remote listings and configured employer boards "
            "can cover more countries; JobAd Links is Sweden-focused."
        )
    international_source_selected = any(
        source in {"remoteok", "greenhouse", "lever", "teamtailor"} for source in selected_sources
    ) or ("arbeitnow" in selected_sources and _normalize(country) in ARBEITNOW_COUNTRIES)
    if _normalize(country) not in {"sweden", "sverige"} and not _is_any_country(country) and not international_source_selected:
        raise JobDiscoveryError(
            "JobAd Links is Sweden-focused. Select Remote OK, Arbeitnow for Germany/UK/France/Switzerland, "
            "or a configured international employer board for this country."
        )
    if len(city) > 100:
        raise JobDiscoveryError("City must be 100 characters or fewer.")
    if not 1 <= limit <= 40:
        raise JobDiscoveryError("Page size must be between 1 and 40.")
    if not 0 <= offset <= 2000:
        raise JobDiscoveryError("Offset must be between 0 and 2000.")
    if work_mode not in {"any", "remote", "hybrid", "on_site"}:
        raise JobDiscoveryError("Unsupported work-mode preference.")

    warnings: list[str] = []
    successful_searches = 0
    selected_ats_sources = [source for source in selected_sources if source in {"greenhouse", "lever", "teamtailor"}]
    if selected_ats_sources:
        try:
            employer_jobs, employer_warnings, configured_boards = fetch_configured_jobs(selected_ats_sources)
        except JobSourceError as exc:
            employer_jobs, employer_warnings, configured_boards = [], [str(exc)], 0
        warnings.extend(employer_warnings)
        if configured_boards:
            successful_searches += max(0, configured_boards - len(employer_warnings))
    else:
        # Public-only searches should not depend on the validity of optional ATS config.
        employer_jobs, employer_warnings, configured_boards = [], [], 0

    remote_jobs: list[JobPosting] = []
    if "remoteok" in selected_sources:
        try:
            remote_jobs = fetch_remote_jobs()
            successful_searches += 1
        except JobSourceError as exc:
            warnings.append(f"Remote OK: {exc}")

    arbeitnow_jobs: list[JobPosting] = []
    country_key = _normalize(country)
    arbeitnow_supported = _is_any_country(country) or country_key in ARBEITNOW_COUNTRIES
    if "arbeitnow" in selected_sources and arbeitnow_supported:
        try:
            arbeitnow_jobs = fetch_arbeitnow_jobs()
            successful_searches += 1
        except JobSourceError as exc:
            warnings.append(f"Arbeitnow: {exc}")
    elif "arbeitnow" in selected_sources:
        warnings.append(
            "Arbeitnow is currently most useful for Germany, the United Kingdom, France and Switzerland; "
            "it was skipped for the selected country."
        )

    page_by_role: list[list[JobPosting]] = []
    role_totals: list[int] = []
    has_more_by_role: list[bool] = []
    filter_rejected = 0
    rejected_by_filter = {"country": 0, "city": 0, "work_mode": 0}

    def passes_location_filters(job: JobPosting) -> bool:
        nonlocal filter_rejected
        if not _matches_country(job, country):
            filter_rejected += 1
            rejected_by_filter["country"] += 1
            return False
        if not _matches_city(job, city, country):
            filter_rejected += 1
            rejected_by_filter["city"] += 1
            return False
        if work_mode != "any" and job.work_mode != work_mode:
            filter_rejected += 1
            rejected_by_filter["work_mode"] += 1
            return False
        return True

    jobtech_selected_and_supported = "jobtech_links" in selected_sources and (
        _normalize(country) in {"sweden", "sverige"} or _is_any_country(country)
    )
    if "jobtech_links" in selected_sources and not jobtech_selected_and_supported:
        warnings.append("JobAd Links is Sweden-focused and was skipped for this country. Keep Remote OK or configured employer boards selected for international results.")

    for role in cleaned_roles:
        query = " ".join(part.strip() for part in (role, city) if part.strip())
        source_total, source_jobs = 0, []
        if jobtech_selected_and_supported:
            try:
                source_total, source_jobs = search_jobs(query=query, limit=limit, offset=offset)
                successful_searches += 1
            except JobSourceError as exc:
                warnings.append(f"JobAd Links ({role}): {exc}")

        selected_public_jobs: list[JobPosting] = []
        for job in source_jobs:
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            if passes_location_filters(job):
                selected_public_jobs.append(job)

        remote_matches = [job for job in remote_jobs if _role_matches(role, job)]
        remote_filtered = []
        for job in remote_matches:
            if not passes_location_filters(job):
                continue
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            remote_filtered.append(job)
        remote_page = remote_filtered[offset:offset + limit]

        arbeitnow_matches = [job for job in arbeitnow_jobs if _role_matches(role, job)]
        arbeitnow_filtered = []
        for job in arbeitnow_matches:
            if not passes_location_filters(job):
                continue
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            arbeitnow_filtered.append(job)
        arbeitnow_page = arbeitnow_filtered[offset:offset + limit]

        employer_matches = [job for job in employer_jobs if _role_matches(role, job)]
        employer_filtered = []
        for job in employer_matches:
            if not passes_location_filters(job):
                continue
            job.search_roles = list(dict.fromkeys([*job.search_roles, role]))
            employer_filtered.append(job)
        employer_page = employer_filtered[offset:offset + limit]

        filtered_public_total = source_total if jobtech_selected_and_supported else 0
        role_totals.append(filtered_public_total + len(remote_filtered) + len(arbeitnow_filtered) + len(employer_filtered))
        has_more_by_role.append(
            (jobtech_selected_and_supported and offset + len(source_jobs) < source_total)
            or offset + limit < len(remote_filtered)
            or offset + limit < len(arbeitnow_filtered)
            or offset + limit < len(employer_filtered)
        )
        page_by_role.append(selected_public_jobs + remote_page + arbeitnow_page + employer_page)

    all_selected_sources_failed = successful_searches == 0 and not employer_jobs and not remote_jobs and not arbeitnow_jobs and warnings
    if all_selected_sources_failed:
        raise JobSourceError("All selected job-source requests failed. " + " | ".join(warnings))

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
                updated = prior.model_copy(update={"search_roles": list(dict.fromkeys(prior.search_roles + job.search_roles))})
                deduped[key] = updated
                for position, existing in enumerate(combined):
                    if _dedupe_key(existing) == key:
                        combined[position] = updated
                        break
                continue
            deduped[key] = job
            combined.append(job)

    total_is_approximate = (
        len(cleaned_roles) > 1 or work_mode != "any" or configured_boards > 0
        or any(source != "jobtech_links" for source in selected_sources)
        or _is_any_country(country)
    )
    if not combined and sum(role_totals) > 0:
        warnings.append(
            "Sources reported matching listings, but none remained after local filters. "
            "Some providers omit structured city metadata; try clearing the city or review the location-filter details."
        )

    filter_notes: list[str] = []
    if city.strip():
        filter_notes.append(
            "City filtering is best-effort: listings with unknown location metadata may be retained when the source cannot confirm a mismatch; verify the original listing."
        )
    if "jobtech_links" in selected_sources:
        filter_notes.append("JobAd Links is a Sweden-focused feed and uses the role plus city as free text, not an exact structured location filter.")
    if "remoteok" in selected_sources:
        filter_notes.append("Remote OK supplies remote roles; CareerMate filters the public feed locally and links to the original listing.")
    if "arbeitnow" in selected_sources:
        filter_notes.append("Arbeitnow results are attributed to their original Arbeitnow job pages; country and work-mode filters are applied locally.")
    if selected_ats_sources:
        filter_notes.append("Greenhouse, Lever and Teamtailor boards are configured per employer; local filters use the location and work-mode metadata each board provides.")
    filter_notes.append("Unknown country/work-mode metadata is not always sufficient to reject a listing. A specific work-mode filter excludes listings whose work mode is unknown.")
    if total_is_approximate:
        filter_notes.append("Totals may be approximate because of local filtering, pagination across feeds, and cross-source duplicates.")

    return {
        "roles": cleaned_roles,
        "country": "Any country" if _is_any_country(country) else country.strip(),
        "city": city.strip(),
        "work_mode": work_mode,
        "total_reported": sum(role_totals),
        "total_is_approximate": total_is_approximate,
        "offset": offset,
        "limit": limit,
        "returned": min(len(combined), limit),
        "has_more": any(has_more_by_role) and offset < 2000,
        "filtered_out": filter_rejected,
        "filtered_out_by": rejected_by_filter,
        "role_searches": len(cleaned_roles),
        "sources": selected_sources,
        "configured_employer_boards": configured_boards,
        "warnings": warnings,
        "filter_note": " ".join(filter_notes),
        "jobs": combined[:limit],
    }
