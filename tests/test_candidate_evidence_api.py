from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.services import candidate_evidence_storage


def test_candidate_evidence_api_create_verify_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate_evidence_storage, "EVIDENCE_PATH", tmp_path / "cv" / "evidence.json")
    client = TestClient(main.app)

    created = client.post("/api/candidate/evidence", json={
        "claim": "Reduced notification delivery failures by 25%",
        "category": "metric",
        "source_type": "experience",
        "source_reference": "Notification platform",
        "supporting_detail": "Measured after implementing retries and failure handling.",
    })
    assert created.status_code == 201
    record = created.json()["evidence"]
    assert record["verified"] is False

    listed = client.get("/api/candidate/evidence")
    assert listed.status_code == 200
    assert listed.json()["pending_count"] == 1

    verified = client.put(f"/api/candidate/evidence/{record['id']}", json={"verified": True})
    assert verified.status_code == 200
    assert verified.json()["evidence"]["verified"] is True
    assert client.get("/api/candidate/evidence").json()["verified_count"] == 1

    deleted = client.delete(f"/api/candidate/evidence/{record['id']}")
    assert deleted.status_code == 200
    assert client.get("/api/candidate/evidence").json()["evidence"] == []


def test_candidate_evidence_requires_valid_claim_and_reports_missing_record():
    client = TestClient(main.app)
    invalid = client.post("/api/candidate/evidence", json={"claim": "x"})
    assert invalid.status_code == 422
    missing = client.put("/api/candidate/evidence/does-not-exist", json={"verified": True})
    assert missing.status_code == 404
