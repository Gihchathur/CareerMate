"""Local workflow state and activity history.

The workflow layer deliberately stores only lightweight triage metadata and
append-only activity events. Job and application records remain in their
existing stores, so this can be introduced without migrating user data.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = BASE_DIR / "data" / "workflow"
TRIAGE_PATH = WORKFLOW_DIR / "job_triage.json"
EVENTS_PATH = WORKFLOW_DIR / "events.json"
_LOCK = threading.RLock()
_ALLOWED_STAGES = {"new", "reviewing", "shortlisted", "skipped"}
_MAX_EVENTS = 1000


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        raw = path.read_text(encoding="utf-8-sig").strip()
        return json.loads(raw) if raw else default
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Workflow data file {path.name} is unreadable or invalid JSON.") from exc


def _atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_job_triage() -> dict[str, dict[str, Any]]:
    with _LOCK:
        payload = _read_json(TRIAGE_PATH, {})
        if not isinstance(payload, dict):
            raise RuntimeError("job_triage.json must contain a JSON object.")
        cleaned: dict[str, dict[str, Any]] = {}
        for job_id, item in payload.items():
            if isinstance(job_id, str) and isinstance(item, dict) and item.get("stage") in _ALLOWED_STAGES:
                cleaned[job_id] = {
                    "job_id": job_id,
                    "stage": item["stage"],
                    "notes": str(item.get("notes", ""))[:4000],
                    "created_at": str(item.get("created_at", "")),
                    "updated_at": str(item.get("updated_at", "")),
                }
        return cleaned


def update_job_triage(job_id: str, stage: str, notes: str | None = None) -> dict[str, Any]:
    if stage not in _ALLOWED_STAGES:
        raise ValueError("Unsupported job triage stage.")
    if not job_id or len(job_id) > 500:
        raise ValueError("Invalid job ID.")
    with _LOCK:
        records = _read_json(TRIAGE_PATH, {})
        if not isinstance(records, dict):
            raise RuntimeError("job_triage.json must contain a JSON object.")
        previous = records.get(job_id) if isinstance(records.get(job_id), dict) else {}
        now = _now()
        record = {
            "job_id": job_id,
            "stage": stage,
            "notes": str(previous.get("notes", "") if notes is None else notes)[:4000],
            "created_at": str(previous.get("created_at") or now),
            "updated_at": now,
        }
        records[job_id] = record
        _atomic_write(TRIAGE_PATH, records)
        return record


def record_event(
    event_type: str,
    title: str,
    detail: str = "",
    *,
    entity_type: str = "workspace",
    entity_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not event_type or len(event_type) > 80:
        raise ValueError("Invalid workflow event type.")
    event = {
        "id": f"event:{uuid4().hex}",
        "event_type": event_type,
        "title": title[:200],
        "detail": detail[:1000],
        "entity_type": entity_type[:40],
        "entity_id": entity_id[:500],
        "metadata": metadata or {},
        "created_at": _now(),
    }
    with _LOCK:
        events = _read_json(EVENTS_PATH, [])
        if not isinstance(events, list):
            raise RuntimeError("events.json must contain a JSON array.")
        safe_events = [item for item in events if isinstance(item, dict)]
        safe_events.insert(0, event)
        _atomic_write(EVENTS_PATH, safe_events[:_MAX_EVENTS])
    return event


def load_events(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with _LOCK:
        events = _read_json(EVENTS_PATH, [])
        if not isinstance(events, list):
            raise RuntimeError("events.json must contain a JSON array.")
        return [item for item in events if isinstance(item, dict)][:limit]
