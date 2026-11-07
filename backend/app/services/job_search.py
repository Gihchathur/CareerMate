"""Local source registry for employer-specific public career-board adapters."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.models.job import JobPosting
from app.services.job_sources.base import JobSourceError, JobSourceIncompleteError, JobSourceStaleCacheError
from app.services.job_sources.greenhouse import fetch_board_jobs
from app.services.job_sources.lever import fetch_site_jobs
from app.services.job_sources.teamtailor import fetch_company_jobs
from app.services.job_sources.public_ats import fetch_public_board

BASE_DIR = Path(__file__).resolve().parents[3]
SOURCE_CONFIG_PATH = BASE_DIR / "data" / "sources.json"
STARTER_CONFIG_PATH = BASE_DIR / "data" / "sources.example.json"
STARTER_SEED_MARKER_PATH = BASE_DIR / "data" / "settings" / "portal-starter-seeded.json"
SUPPORTED_ATS = ("greenhouse", "lever", "teamtailor", "ashby", "smartrecruiters", "workable", "recruitee", "breezy", "personio", "workday")
PUBLIC_ATS = ("ashby", "smartrecruiters", "workable", "recruitee", "breezy", "personio", "workday")


def validate_source_config(payload: Any) -> dict[str, Any]:
    """Validate and normalize the local employer-board configuration."""
    if not isinstance(payload, dict):
        raise JobSourceError("Job source configuration must be a JSON object.")
    rules = {
        "greenhouse": {"fields": ("board_token", "company", "country"), "required": ("board_token",), "regions": None},
        "lever": {"fields": ("site", "company", "country", "region"), "required": ("site",), "regions": {"global", "eu"}},
        "teamtailor": {"fields": ("company", "country", "api_key_env", "region"), "required": ("company", "api_key_env"), "regions": {"eu", "na", "apac"}},
        **{source: {"fields": ("slug", "company", "country"), "required": ("slug",), "regions": None} for source in PUBLIC_ATS},
    }
    normalized: dict[str, list[dict[str, Any]]] = {source: [] for source in SUPPORTED_ATS}
    for source, spec in rules.items():
        entries = payload.get(source, [])
        if not isinstance(entries, list):
            raise JobSourceError(f"The '{source}' setting must be a list.")
        if len(entries) > 100:
            raise JobSourceError(f"At most 100 {source} employer boards can be configured.")
        for index, item in enumerate(entries, start=1):
            if not isinstance(item, dict):
                raise JobSourceError(f"Entry {index} under '{source}' must be an object.")
            enabled = item.get("enabled", False) is True
            clean: dict[str, Any] = {"enabled": enabled}
            for field_name in spec["fields"]:
                value = item.get(field_name, "")
                if not isinstance(value, str):
                    raise JobSourceError(f"Entry {index} under '{source}' has an invalid '{field_name}' value.")
                value = value.strip()
                if len(value) > 200:
                    raise JobSourceError(f"Entry {index} under '{source}' has an overly long '{field_name}' value.")
                clean[field_name] = value
            # Human-readable portal metadata lives beside the ATS identifier.
            # It is optional, local-only, and never used as an API credential.
            for field_name in ("career_url", "jobs_url"):
                value = item.get(field_name, "")
                if not isinstance(value, str):
                    raise JobSourceError(f"Entry {index} under '{source}' has an invalid '{field_name}' value.")
                value = value.strip()
                if len(value) > 1000:
                    raise JobSourceError(f"Entry {index} under '{source}' has an overly long '{field_name}' value.")
                if value:
                    parsed = urlparse(value)
                    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                        raise JobSourceError(f"Entry {index} under '{source}' requires '{field_name}' to be a public HTTPS URL.")
                clean[field_name] = value
            starter_sample = item.get("starter_sample", False)
            if not isinstance(starter_sample, bool):
                raise JobSourceError(f"Entry {index} under '{source}' has an invalid 'starter_sample' value.")
            if starter_sample:
                clean["starter_sample"] = True
            notes = item.get("notes", "")
            if not isinstance(notes, str):
                raise JobSourceError(f"Entry {index} under '{source}' has an invalid 'notes' value.")
            notes = notes.strip()
            if len(notes) > 1000:
                raise JobSourceError(f"Entry {index} under '{source}' has overly long notes.")
            clean["notes"] = notes
            if source in {"lever", "teamtailor"}:
                default_region = "global" if source == "lever" else "eu"
                clean["region"] = clean.get("region") or default_region
            if enabled and source in PUBLIC_ATS:
                slug = clean.get("slug", "")
                if source == "workday":
                    parsed = urlparse(slug if "://" in slug else "https://" + slug)
                    if parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com", parsed.netloc, re.I) or not parsed.path.strip("/"):
                        raise JobSourceError("Workday requires a public HTTPS careers URL on *.wdN.myworkdayjobs.com with a site path.")
                elif not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", slug):
                    raise JobSourceError(f"{source.title()} board slug may contain only letters, numbers, underscores and hyphens.")
            if enabled:
                for field_name in spec["required"]:
                    if not clean.get(field_name):
                        raise JobSourceError(f"Enabled {source} entry {index} requires a non-empty '{field_name}' value.")
                region = str(clean.get("region", "global" if source == "lever" else "eu")).casefold()
                if spec["regions"] is not None and region not in spec["regions"]:
                    allowed = ", ".join(sorted(spec["regions"]))
                    raise JobSourceError(f"Enabled {source} entry {index} has an unsupported region '{region}'. Use {allowed}.")
                if source == "teamtailor" and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", clean["api_key_env"]):
                    raise JobSourceError("Teamtailor API key must be an environment variable name, never the key value itself.")
            if source == "lever" and clean.get("region") and clean["region"].casefold() not in {"global", "eu"}:
                raise JobSourceError("Lever region must be 'global' or 'eu'.")
            if source == "teamtailor" and clean.get("region") and clean["region"].casefold() not in {"eu", "na", "apac"}:
                raise JobSourceError("Teamtailor region must be 'eu', 'na', or 'apac'.")
            normalized[source].append(clean)
    return normalized


def _empty_source_config() -> dict[str, list[dict[str, Any]]]:
    return {source: [] for source in SUPPORTED_ATS}


def _board_identity(provider: str, board: dict[str, Any]) -> str:
    if provider == "greenhouse":
        identifier = board.get("board_token", "")
    elif provider == "lever":
        identifier = board.get("site", "")
    elif provider == "teamtailor":
        identifier = board.get("company", "")
    else:
        identifier = board.get("slug", "")
    return str(identifier).strip().casefold()


def _portal_id(provider: str, board: dict[str, Any]) -> str:
    """Return the stable, non-secret identifier used by Explore for one company board."""
    identity = _board_identity(provider, board)
    return f"{provider}:{identity}" if identity else ""


def _write_source_config(normalized: dict[str, Any]) -> None:
    SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SOURCE_CONFIG_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(SOURCE_CONFIG_PATH)


STARTER_PORTALS_VERSION = 3


def _starter_portals_seed_version() -> int:
    """Read the one-time seed marker; missing or malformed markers are version zero."""
    try:
        marker = json.loads(STARTER_SEED_MARKER_PATH.read_text(encoding="utf-8-sig"))
        return int(marker.get("starter_portals_version", 0)) if isinstance(marker, dict) else 0
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0


def _mark_starter_portals_initialized() -> None:
    STARTER_SEED_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = STARTER_SEED_MARKER_PATH.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps({"initialized": True, "starter_portals_version": STARTER_PORTALS_VERSION}, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(STARTER_SEED_MARKER_PATH)


def _merge_starter_portals(current: dict[str, Any]) -> dict[str, Any]:
    """Add or upgrade the five starter employers once, without overwriting user boards.

    Version 3 is an additive upgrade for installs that already wrote a version 2
    marker while their portal registry was empty. The five starter portals are
    added once without replacing any user-defined board or its configuration.
    """
    if (
        (_starter_portals_seed_version() >= STARTER_PORTALS_VERSION and SOURCE_CONFIG_PATH.exists())
        or not STARTER_CONFIG_PATH.is_file()
    ):
        return current
    try:
        starter_payload = json.loads(STARTER_CONFIG_PATH.read_text(encoding="utf-8-sig"))
        starter = validate_source_config(starter_payload)
    except (OSError, json.JSONDecodeError, JobSourceError):
        # A broken optional example file must never prevent the app from starting.
        return current

    merged = {provider: list(current.get(provider, [])) for provider in SUPPORTED_ATS}
    existing = {
        (provider, _board_identity(provider, board))
        for provider in SUPPORTED_ATS
        for board in merged[provider]
    }
    added = 0
    for provider in SUPPORTED_ATS:
        for board in starter.get(provider, []):
            identity = _board_identity(provider, board)
            if not identity or (provider, identity) in existing:
                continue
            merged[provider].append(board)
            existing.add((provider, identity))
            added += 1

    # Persist the merged registry only when a starter board was actually added.
    # Existing user entries are retained exactly as normalized by the validator.
    if added:
        normalized = validate_source_config(merged)
        _write_source_config(normalized)
        merged = normalized
    _mark_starter_portals_initialized()
    return merged


def load_source_config() -> dict[str, Any]:
    """Load local ATS settings and install starter portals once on first setup.

    The one-time seed is additive: an existing user's boards are never replaced,
    duplicate identifiers are skipped, and removing the starter portals later
    does not cause them to reappear.
    """
    if not SOURCE_CONFIG_PATH.exists():
        config = _empty_source_config()
    else:
        try:
            contents = SOURCE_CONFIG_PATH.read_text(encoding="utf-8-sig").strip()
        except OSError as exc:
            raise JobSourceError("Could not read data/sources.json.") from exc
        if not contents:
            config = _empty_source_config()
        else:
            try:
                payload = json.loads(contents)
            except json.JSONDecodeError as exc:
                raise JobSourceError(f"data/sources.json is invalid JSON at line {exc.lineno}, column {exc.colno}.") from exc
            config = validate_source_config(payload)
    return _merge_starter_portals(config)


def save_source_config(payload: Any) -> dict[str, Any]:
    """Validate and atomically save public board identifiers and environment-variable names."""
    normalized = validate_source_config(payload)
    _write_source_config(normalized)
    # An explicit user save should permanently suppress automatic re-seeding.
    _mark_starter_portals_initialized()
    return normalized


def source_status() -> dict[str, object]:
    """Return safe connection metadata; never return tokens or secret values."""
    config = load_source_config()
    greenhouse = [item for item in config.get("greenhouse", []) if item.get("enabled") is True and item.get("board_token")]
    lever = [item for item in config.get("lever", []) if item.get("enabled") is True and item.get("site")]
    teamtailor = [item for item in config.get("teamtailor", []) if item.get("enabled") is True and item.get("api_key_env")]
    missing_teamtailor_keys = [
        item for item in teamtailor
        if not os.getenv(str(item.get("api_key_env", "")).strip(), "")
    ]
    ready_teamtailor = [item for item in teamtailor if item not in missing_teamtailor_keys]
    return {
        "jobtech_links": {"configured": True, "employers": None, "requires_api_key": False},
        "remoteok": {"configured": True, "employers": None, "requires_api_key": False},
        "arbeitnow": {"configured": True, "employers": None, "requires_api_key": False},
        "greenhouse": {"configured": bool(greenhouse), "employers": len(greenhouse), "requires_api_key": False},
        "lever": {"configured": bool(lever), "employers": len(lever), "requires_api_key": False},
        "teamtailor": {
            "configured": bool(teamtailor),
            "employers": len(teamtailor),
            "requires_api_key": True,
            # One configured board with a key is enough to make the provider
            # selectable; other company boards are still reported individually
            # as needing setup and will be skipped by the adapter.
            "credentials_ready": bool(ready_teamtailor),
            "missing_credentials": len(missing_teamtailor_keys),
        },
        **{source: {"configured": any(x.get("enabled") and x.get("slug") for x in config.get(source, [])),
                    "employers": sum(1 for x in config.get(source, []) if x.get("enabled") and x.get("slug")),
                    "requires_api_key": False} for source in PUBLIC_ATS},
    }


def list_configured_portals(selected_portal_ids: set[str] | list[str] | None = None) -> list[dict[str, str]]:
    """Return safe, selected company-board metadata for search coverage reporting."""
    config = load_source_config()
    selected = (
        {str(item).strip().casefold() for item in selected_portal_ids if str(item).strip()}
        if selected_portal_ids is not None else None
    )
    portals: list[dict[str, str]] = []
    for provider in SUPPORTED_ATS:
        for board in config.get(provider, []):
            if board.get("enabled") is not True:
                continue
            portal_id = _portal_id(provider, board)
            if not portal_id or (selected is not None and portal_id not in selected):
                continue
            portals.append({
                "id": portal_id,
                "provider": provider,
                "company": str(board.get("company") or _board_identity(provider, board)).strip(),
            })
    return portals


def _append_board_jobs(
    jobs: list[JobPosting],
    warnings: list[str],
    provider: str,
    board: dict[str, Any],
    fetcher,
) -> None:
    """Append complete or usable partial board results with stable portal identity."""
    label = str(board.get("company") or _board_identity(provider, board)).strip() or provider.title()
    portal_id = _portal_id(provider, board)
    try:
        fetched = fetcher()
    except JobSourceIncompleteError as exc:
        fetched = exc.partial_jobs
        warnings.append(f"{provider.title()} ({label}): {exc}")
    except JobSourceStaleCacheError as exc:
        fetched = exc.cached_jobs
        warnings.append(f"{provider.title()} ({label}): {exc}")
    except JobSourceError as exc:
        warnings.append(f"{provider.title()} ({label}): {exc}")
        return

    fetched_at = datetime.now(timezone.utc).isoformat()
    for job in fetched:
        jobs.append(job.model_copy(update={
            "portal_id": portal_id,
            "portal_name": label,
            "source_fetched_at": job.source_fetched_at or fetched_at,
        }))


def fetch_configured_jobs(
    selected_sources: set[str] | list[str] | None = None,
    selected_portal_ids: set[str] | list[str] | None = None,
    *,
    force_refresh: bool = False,
) -> tuple[list[JobPosting], list[str], int]:
    """Fetch the complete published inventory from selected enabled employer boards.

    Every board is isolated: one provider outage does not discard other companies'
    results. Partial pagination and stale-cache use are returned as visible warnings
    while preserving the jobs we were still able to retrieve.
    """
    config = load_source_config()
    selected = set(selected_sources) if selected_sources is not None else set(SUPPORTED_ATS)
    selected_portals = (
        {str(item).strip().casefold() for item in selected_portal_ids if str(item).strip()}
        if selected_portal_ids is not None else None
    )

    def portal_is_selected(provider: str, board: dict[str, Any]) -> bool:
        return selected_portals is None or _portal_id(provider, board) in selected_portals

    jobs: list[JobPosting] = []
    warnings: list[str] = []
    configured_count = 0
    initial_counts = {
        source: sum(
            1 for item in config.get(source, [])
            if item.get("enabled") is True
            and portal_is_selected(source, item)
            and (
                bool(str(item.get("board_token", "")).strip()) if source == "greenhouse"
                else bool(str(item.get("site", "")).strip()) if source == "lever"
                else bool(str(item.get("api_key_env", "")).strip()) if source == "teamtailor" else bool(str(item.get("slug", "")).strip())
            )
        )
        for source in SUPPORTED_ATS
    }
    for source in sorted(selected.intersection(SUPPORTED_ATS)):
        if source not in PUBLIC_ATS and initial_counts[source] == 0:
            suffix = "selected " if selected_portals is not None else ""
            warnings.append(f"No {suffix}enabled {source.title()} employer portals are configured in data/sources.json.")

    if "greenhouse" in selected:
        for item in config.get("greenhouse", []):
            if item.get("enabled") is not True or not str(item.get("board_token", "")).strip() or not portal_is_selected("greenhouse", item):
                continue
            configured_count += 1
            token = str(item["board_token"]).strip()
            _append_board_jobs(jobs, warnings, "greenhouse", item, lambda token=token, item=item: fetch_board_jobs(
                token, company_name=str(item.get("company", "")), default_country=str(item.get("country", "")),
            ))

    if "lever" in selected:
        for item in config.get("lever", []):
            if item.get("enabled") is not True or not str(item.get("site", "")).strip() or not portal_is_selected("lever", item):
                continue
            configured_count += 1
            site = str(item["site"]).strip()
            _append_board_jobs(jobs, warnings, "lever", item, lambda site=site, item=item: fetch_site_jobs(
                site, company_name=str(item.get("company", "")), region=str(item.get("region", "global")),
                default_country=str(item.get("country", "")),
            ))

    if "teamtailor" in selected:
        for item in config.get("teamtailor", []):
            if item.get("enabled") is not True or not str(item.get("api_key_env", "")).strip() or not portal_is_selected("teamtailor", item):
                continue
            configured_count += 1
            company = str(item.get("company", "")).strip()
            key_env = str(item["api_key_env"]).strip()
            api_key = os.getenv(key_env, "")
            if not api_key:
                warnings.append(f"Teamtailor ({company or key_env}): environment variable {key_env} is not set.")
                continue
            _append_board_jobs(jobs, warnings, "teamtailor", item, lambda item=item, api_key=api_key, company=company: fetch_company_jobs(
                api_key=api_key, company_name=company, region=str(item.get("region", "eu")),
                default_country=str(item.get("country", "")),
            ))

    for source in PUBLIC_ATS:
        if source not in selected:
            continue
        boards = [
            item for item in config.get(source, [])
            if item.get("enabled") is True and item.get("slug") and portal_is_selected(source, item)
        ]
        if not boards:
            suffix = "selected " if selected_portals is not None else ""
            warnings.append(f"No {suffix}enabled {source.title()} employer portals are configured in data/sources.json.")
        for item in boards:
            configured_count += 1
            _append_board_jobs(
                jobs, warnings, source, item,
                lambda source=source, item=item: fetch_public_board(source, item, force_refresh=force_refresh),
            )

    return jobs, warnings, configured_count
