
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[3]

JOBS_PATH = BASE_DIR / "data" / "jobs" / "jobs.json"


def _dedupe_key(job: dict[str, Any]) -> str:
    """Create a consistent key for repeated search results."""

    title = " ".join(job.get("title", "").lower().split())
    company = " ".join(job.get("company", "").lower().split())
    location = " ".join(job.get("location", "").lower().split())

    if (
        title
        and company
        and company != "company not specified"
    ):
        return f"{title}|{company}|{location}"

    return job.get("id", "")


def load_saved_jobs() -> list[dict[str, Any]]:
    """Read previously saved job listings."""

    if not JOBS_PATH.exists():
        return []

    try:
        data = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Could not read {JOBS_PATH}: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            "jobs.json must contain a JSON array."
        )

    return [
        job for job in data
        if isinstance(job, dict)
    ]


def save_jobs(
    incoming_jobs: list[dict[str, Any]],
) -> int:
    """Merge search results with saved jobs and remove duplicates."""

    existing_jobs = load_saved_jobs()
    merged: dict[str, dict[str, Any]] = {}

    for job in existing_jobs + incoming_jobs:
        key = _dedupe_key(job)

        if not key:
            continue

        if key in merged:
            # Keep existing information where the new result
            # doesn't provide a value.
            merged[key] = {
                **merged[key],
                **{
                    name: value
                    for name, value in job.items()
                    if value not in ("", None, [])
                },
            }
        else:
            merged[key] = job

    saved_jobs = list(merged.values())

    JOBS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = JOBS_PATH.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(saved_jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temporary_path.replace(JOBS_PATH)

    return len(saved_jobs)
