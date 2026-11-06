from __future__ import annotations

import json

import pytest

from app.services import candidate_evidence_storage as storage


def test_evidence_is_created_pending_and_persisted(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "EVIDENCE_PATH", tmp_path / "cv" / "evidence.json")
    record = storage.create_evidence({
        "claim": "Reduced notification failures by 25%",
        "category": "metric",
        "source_type": "experience",
        "source_reference": "Notification platform",
        "supporting_detail": "Measured before and after the retry implementation.",
    })
    assert record["verified"] is False
    assert record["id"]
    assert storage.load_evidence() == [record]
    assert json.loads(storage.EVIDENCE_PATH.read_text())[0]["claim"] == record["claim"]


def test_evidence_can_be_verified_updated_and_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "EVIDENCE_PATH", tmp_path / "evidence.json")
    record = storage.create_evidence({"claim": "Built a Kubernetes deployment pipeline", "category": "experience"})
    updated = storage.update_evidence(record["id"], {"verified": True, "supporting_detail": "Supported by the project delivery record."})
    assert updated is not None
    assert updated["verified"] is True
    assert updated["supporting_detail"] == "Supported by the project delivery record."
    assert storage.delete_evidence(record["id"]) is True
    assert storage.load_evidence() == []
    assert storage.delete_evidence(record["id"]) is False


def test_invalid_evidence_store_is_not_silently_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "evidence.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(storage, "EVIDENCE_PATH", path)
    with pytest.raises(RuntimeError):
        storage.load_evidence()
