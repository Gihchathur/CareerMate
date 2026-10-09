import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[3]
JOBS_PATH = BASE_DIR / "data" / "jobs" / "jobs.json"


def _normal(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def _dedupe_key(job: dict[str, Any]) -> str:
    source = _normal(job.get("source"))
    source_id = _normal(job.get("source_id"))
    if source and source_id:
        return f"source:{source}:{source_id}"

    url = _normal(job.get("apply_url") or job.get("source_url"))
    if url:
        return f"url:{url.rstrip('/')}"

    title = _normal(job.get("title"))
    company = _normal(job.get("company"))
    location = _normal(job.get("location"))
    if title and company and company != "company not specified":
        return f"fallback:{title}|{company}|{location}"

    return _normal(job.get("id"))


def load_saved_jobs() -> list[dict[str, Any]]:
    """Load jobs from JSON; missing or blank files mean no saved jobs."""
    if not JOBS_PATH.exists():
        return []

    try:
        content = JOBS_PATH.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        raise RuntimeError(f"Could not read saved jobs: {exc}") from exc

    if not content:
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Saved jobs file contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}. Back up and repair the file before saving."
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError("jobs.json must contain a JSON array.")
    if not all(isinstance(item, dict) for item in data):
        raise RuntimeError("Each entry in jobs.json must be a JSON object.")
    return data


def _merge_job(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = {
        **old,
        **{name: value for name, value in new.items() if value not in ("", None, [])},
    }

    # Keep all role queries that surfaced a job when the same result appears
    # in searches for multiple roles.
    old_roles = old.get("search_roles", [])
    new_roles = new.get("search_roles", [])
    if not isinstance(old_roles, list):
        old_roles = []
    if not isinstance(new_roles, list):
        new_roles = []
    merged_roles = list(dict.fromkeys(
        role for role in [*old_roles, *new_roles]
        if isinstance(role, str) and role.strip()
    ))
    if merged_roles:
        merged["search_roles"] = merged_roles

    return merged


def save_jobs(incoming_jobs: list[dict[str, Any]]) -> int:
    """Merge search results with saved JSON, retaining source IDs and role labels."""
    merged: dict[str, dict[str, Any]] = {}
    for job in [*load_saved_jobs(), *incoming_jobs]:
        key = _dedupe_key(job)
        if not key:
            continue
        if key in merged:
            merged[key] = _merge_job(merged[key], job)
        else:
            merged[key] = job

    saved = list(merged.values())
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = JOBS_PATH.with_suffix(".tmp")
    try:
        temporary_path.write_text(
            json.dumps(saved, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(JOBS_PATH)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return len(saved)
