import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models.application import ApplicationRecord

BASE_DIR = Path(__file__).resolve().parents[3]
APPLICATIONS_PATH = BASE_DIR / "data" / "applications" / "applications.json"
_STORAGE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_applications() -> list[dict[str, Any]]:
    """Load local application records; a missing or empty file means no records."""
    if not APPLICATIONS_PATH.exists():
        return []

    try:
        raw = APPLICATIONS_PATH.read_text(encoding="utf-8-sig")
        if not raw.strip():
            return []
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("The local applications file is unreadable or invalid JSON.") from exc

    if not isinstance(payload, list):
        raise RuntimeError("The local applications file must contain a JSON array.")

    records: list[dict[str, Any]] = []
    try:
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("Application entries must be JSON objects.")
            records.append(ApplicationRecord.model_validate(item).model_dump())
    except (ValidationError, TypeError, ValueError) as exc:
        raise RuntimeError("The local applications file contains an invalid record.") from exc
    return records


def save_applications(records: list[dict[str, Any]]) -> None:
    """Validate and atomically persist all application records as local JSON."""
    validated = [ApplicationRecord.model_validate(item).model_dump() for item in records]
    content = json.dumps(validated, ensure_ascii=False, indent=2) + "\n"
    APPLICATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = APPLICATIONS_PATH.with_suffix(APPLICATIONS_PATH.suffix + ".tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8")
        temporary_path.replace(APPLICATIONS_PATH)
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError("Could not save application records locally.") from exc


def get_application(application_id: str) -> dict[str, Any] | None:
    return next((item for item in load_applications() if item["id"] == application_id), None)


def create_application(record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Create once per job ID; repeated attempts return the existing record."""
    validated = ApplicationRecord.model_validate(record).model_dump()
    with _STORAGE_LOCK:
        records = load_applications()
        existing = next((item for item in records if item["job_id"] == validated["job_id"]), None)
        if existing:
            return existing, False
        records.insert(0, validated)
        save_applications(records)
    return validated, True


def update_application(application_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    with _STORAGE_LOCK:
        records = load_applications()
        for index, record in enumerate(records):
            if record["id"] != application_id:
                continue
            merged = {**record, **updates}
            merged["updated_at"] = utc_now()
            try:
                validated = ApplicationRecord.model_validate(merged).model_dump()
            except ValidationError as exc:
                raise RuntimeError("The application changes exceed the supported record limits.") from exc
            records[index] = validated
            save_applications(records)
            return validated
    return None
