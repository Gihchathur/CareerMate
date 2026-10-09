"""Local source registry for employer-specific public career-board adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.models.job import JobPosting
from app.services.job_sources.base import JobSourceError
from app.services.job_sources.greenhouse import fetch_board_jobs
from app.services.job_sources.lever import fetch_site_jobs
from app.services.job_sources.teamtailor import fetch_company_jobs

BASE_DIR = Path(__file__).resolve().parents[3]
SOURCE_CONFIG_PATH = BASE_DIR / "data" / "sources.json"
SUPPORTED_ATS = ("greenhouse", "lever", "teamtailor")


def load_source_config() -> dict[str, Any]:
    """Load and validate private per-user source settings from data/sources.json."""
    if not SOURCE_CONFIG_PATH.exists():
        return {}
    try:
        contents = SOURCE_CONFIG_PATH.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        raise JobSourceError("Could not read data/sources.json.") from exc
    if not contents:
        return {}
    try:
        payload = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise JobSourceError(
            f"data/sources.json is invalid JSON at line {exc.lineno}, column {exc.colno}."
        ) from exc
    if not isinstance(payload, dict):
        raise JobSourceError("data/sources.json must contain a JSON object.")

    schema = {
        "greenhouse": {"required": ("board_token",), "regions": None},
        "lever": {"required": ("site",), "regions": {"global", "eu"}},
        "teamtailor": {"required": ("company", "api_key_env"), "regions": {"eu", "na", "apac"}},
    }
    for source, rules in schema.items():
        entries = payload.get(source, [])
        if not isinstance(entries, list):
            raise JobSourceError(f"The '{source}' setting in data/sources.json must be a list.")
        for index, item in enumerate(entries, start=1):
            if not isinstance(item, dict):
                raise JobSourceError(f"Entry {index} under '{source}' must be an object.")
            if item.get("enabled") is not True:
                continue
            for field in rules["required"]:
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise JobSourceError(
                        f"Enabled {source} entry {index} requires a non-empty '{field}' value."
                    )
            allowed_regions = rules["regions"]
            if allowed_regions is not None:
                region = str(item.get("region", "global" if source == "lever" else "eu")).strip().casefold()
                if region not in allowed_regions:
                    allowed = ", ".join(sorted(allowed_regions))
                    raise JobSourceError(
                        f"Enabled {source} entry {index} has an unsupported region '{region}'. Use {allowed}."
                    )
    return payload


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
    return {
        "jobtech_links": {"configured": True, "employers": None, "requires_api_key": False},
        "greenhouse": {"configured": bool(greenhouse), "employers": len(greenhouse), "requires_api_key": False},
        "lever": {"configured": bool(lever), "employers": len(lever), "requires_api_key": False},
        "teamtailor": {
            "configured": bool(teamtailor),
            "employers": len(teamtailor),
            "requires_api_key": True,
            "credentials_ready": bool(teamtailor) and not missing_teamtailor_keys,
            "missing_credentials": len(missing_teamtailor_keys),
        },
    }


def fetch_configured_jobs(
    selected_sources: set[str] | list[str] | None = None,
) -> tuple[list[JobPosting], list[str], int]:
    """Fetch jobs from selected, enabled employer ATS boards.

    If `selected_sources` is omitted, all optional ATS sources are considered.
    Returns normalized jobs, warnings from failed individual boards, and the
    number of enabled board definitions. Each source is fault-tolerant, so an
    unavailable employer board does not block successful results elsewhere.
    """
    config = load_source_config()
    selected = set(selected_sources) if selected_sources is not None else set(SUPPORTED_ATS)
    jobs: list[JobPosting] = []
    warnings: list[str] = []
    configured_count = 0
    initial_counts = {
        source: sum(
            1 for item in config.get(source, [])
            if item.get("enabled") is True
            and (
                bool(str(item.get("board_token", "")).strip()) if source == "greenhouse"
                else bool(str(item.get("site", "")).strip()) if source == "lever"
                else bool(str(item.get("api_key_env", "")).strip())
            )
        )
        for source in SUPPORTED_ATS
    }
    for source in sorted(selected.intersection(SUPPORTED_ATS)):
        if initial_counts[source] == 0:
            warnings.append(f"No enabled {source.title()} employer boards are configured in data/sources.json.")

    if "greenhouse" in selected:
        for item in config.get("greenhouse", []):
            if item.get("enabled") is not True or not str(item.get("board_token", "")).strip():
                continue
            configured_count += 1
            token = str(item["board_token"]).strip()
            try:
                jobs.extend(fetch_board_jobs(
                    token,
                    company_name=str(item.get("company", "")),
                    default_country=str(item.get("country", "")),
                ))
            except JobSourceError as exc:
                warnings.append(f"Greenhouse ({item.get('company') or token}): {exc}")
    if "lever" in selected:
        for item in config.get("lever", []):
            if item.get("enabled") is not True or not str(item.get("site", "")).strip():
                continue
            configured_count += 1
            site = str(item["site"]).strip()
            try:
                jobs.extend(fetch_site_jobs(
                    site,
                    company_name=str(item.get("company", "")),
                    region=str(item.get("region", "global")),
                    default_country=str(item.get("country", "")),
                ))
            except JobSourceError as exc:
                warnings.append(f"Lever ({item.get('company') or site}): {exc}")
    if "teamtailor" in selected:
        for item in config.get("teamtailor", []):
            if item.get("enabled") is not True or not str(item.get("api_key_env", "")).strip():
                continue
            configured_count += 1
            company = str(item.get("company", "")).strip()
            key_env = str(item["api_key_env"]).strip()
            api_key = os.getenv(key_env, "")
            if not api_key:
                warnings.append(f"Teamtailor ({company or key_env}): environment variable {key_env} is not set.")
                continue
            try:
                jobs.extend(fetch_company_jobs(
                    api_key=api_key,
                    company_name=company,
                    region=str(item.get("region", "eu")),
                    default_country=str(item.get("country", "")),
                ))
            except JobSourceError as exc:
                warnings.append(f"Teamtailor ({company or key_env}): {exc}")
    return jobs, warnings, configured_count
