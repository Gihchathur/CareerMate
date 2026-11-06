"""Atomic, local-only storage for candidate evidence records."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.models.candidate_evidence import CandidateEvidenceRecord

BASE_DIR = Path(__file__).resolve().parents[3]
EVIDENCE_PATH = BASE_DIR / "data" / "cv" / "evidence.json"
_STORAGE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_evidence() -> list[dict[str, Any]]:
    if not EVIDENCE_PATH.exists():
        return []
    try:
        raw = EVIDENCE_PATH.read_text(encoding="utf-8-sig")
        payload = json.loads(raw) if raw.strip() else []
        if not isinstance(payload, list):
            raise ValueError("Candidate evidence must be a JSON array.")
        return [CandidateEvidenceRecord.model_validate(item).model_dump() for item in payload]
    except (OSError, json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        raise RuntimeError("The local candidate evidence file is unreadable or invalid.") from exc


def _save(records: list[dict[str, Any]]) -> None:
    validated = [CandidateEvidenceRecord.model_validate(item).model_dump() for item in records]
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE_PATH.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(validated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(EVIDENCE_PATH)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Could not save candidate evidence locally.") from exc


def create_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    record = CandidateEvidenceRecord(
        id=uuid4().hex,
        verified=False,
        created_at=now,
        updated_at=now,
        **payload,
    ).model_dump()
    with _STORAGE_LOCK:
        records = load_evidence()
        records.insert(0, record)
        _save(records)
    return record


def update_evidence(evidence_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    with _STORAGE_LOCK:
        records = load_evidence()
        for index, record in enumerate(records):
            if record["id"] != evidence_id:
                continue
            merged = {**record, **updates, "updated_at": _now()}
            try:
                validated = CandidateEvidenceRecord.model_validate(merged).model_dump()
            except ValidationError as exc:
                raise ValueError("The evidence changes are invalid.") from exc
            records[index] = validated
            _save(records)
            return validated
    return None


def delete_evidence(evidence_id: str) -> bool:
    with _STORAGE_LOCK:
        records = load_evidence()
        updated = [record for record in records if record["id"] != evidence_id]
        if len(updated) == len(records):
            return False
        _save(updated)
    return True
