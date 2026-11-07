from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.services import application_storage, job_storage, workflow_storage


def _job(job_id: str, title: str = "Platform Engineer") -> dict[str, object]:
    return {
        "id": job_id,
        "source": "Remote OK",
        "source_id": f"remote-{job_id}",
        "title": title,
        "company": "Example AB",
        "location": "Stockholm, Sweden",
        "description": "Kubernetes, Azure, CI/CD and observability experience required.",
        "published_at": "2026-11-06T10:00:00Z",
        "source_url": "https://example.com/jobs/1",
        "apply_url": "https://example.com/jobs/1/apply",
    }


def _isolate_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(job_storage, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", tmp_path / "applications.json")
    monkeypatch.setattr(workflow_storage, "TRIAGE_PATH", tmp_path / "workflow" / "job_triage.json")
    monkeypatch.setattr(workflow_storage, "EVENTS_PATH", tmp_path / "workflow" / "events.json")


def test_workflow_inbox_returns_untracked_jobs_and_counts(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    job_storage.save_jobs([_job("job-1"), _job("job-2", "Backend Engineer")])
    workflow_storage.update_job_triage("job-2", "reviewing")

    client = TestClient(main.app)
    response = client.get("/api/workflow/inbox")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["counts"] == {"new": 1, "reviewing": 1, "shortlisted": 0, "skipped": 0}
    assert {item["job"]["id"] for item in payload["items"]} == {"job-1", "job-2"}


def test_workflow_triage_updates_state_and_activity(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    job_storage.save_jobs([_job("job-1")])
    client = TestClient(main.app)

    response = client.put("/api/workflow/jobs/job-1/triage", json={"stage": "shortlisted"})

    assert response.status_code == 200
    assert response.json()["triage"]["stage"] == "shortlisted"
    activity = client.get("/api/workflow/activity")
    assert activity.status_code == 200
    assert activity.json()["events"][0]["event_type"] == "job_triage_updated"


def test_workflow_triage_rejects_missing_jobs_and_invalid_stage(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    client = TestClient(main.app)

    missing = client.put("/api/workflow/jobs/missing/triage", json={"stage": "reviewing"})
    invalid = client.put("/api/workflow/jobs/missing/triage", json={"stage": "applied"})

    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_workflow_inbox_excludes_jobs_already_in_pipeline(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    job_storage.save_jobs([_job("job-1"), _job("job-2")])
    now = application_storage.utc_now()
    application_storage.create_application({
        "id": "application:1", "job_id": "job-2", "company": "Example AB",
        "title": "Backend Engineer", "location": "Stockholm", "source": "Remote OK",
        "job_url": "https://example.com/jobs/1", "source_url": "https://example.com/jobs/1",
        "job_description": "Description", "status": "saved", "notes": "",
        "follow_up_date": "", "cover_letter": "", "answers": [],
        "created_at": now, "updated_at": now, "applied_at": "",
    })

    response = TestClient(main.app).get("/api/workflow/inbox")
    assert response.status_code == 200
    assert [item["job"]["id"] for item in response.json()["items"]] == ["job-1"]


def test_workflow_event_limit_is_bounded(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    for index in range(5):
        workflow_storage.record_event("test", f"Event {index}")
    assert len(workflow_storage.load_events(2)) == 2


def test_workflow_inbox_sorts_newest_publication_first(tmp_path, monkeypatch):
    _isolate_workflow(tmp_path, monkeypatch)
    job_storage.save_jobs([
        {**_job("older"), "published_at": "2026-10-01T09:00:00Z"},
        {**_job("newer"), "published_at": "2026-11-05T09:00:00Z"},
    ])

    response = TestClient(main.app).get("/api/workflow/inbox")

    assert response.status_code == 200
    assert [item["job"]["id"] for item in response.json()["items"]] == ["newer", "older"]


def test_workspace_reset_clears_saved_jobs_and_the_workflow_inbox(tmp_path, monkeypatch):
    """A reset must remove jobs from disk and the inbox endpoint must return empty."""
    data_root = tmp_path / "data"
    monkeypatch.setattr(main, "DATA_DIR", data_root)
    monkeypatch.setattr(job_storage, "JOBS_PATH", data_root / "jobs" / "jobs.json")
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", data_root / "applications" / "applications.json")
    monkeypatch.setattr(workflow_storage, "TRIAGE_PATH", data_root / "workflow" / "job_triage.json")
    monkeypatch.setattr(workflow_storage, "EVENTS_PATH", data_root / "workflow" / "events.json")
    job_storage.save_jobs([_job("stale-job-1"), _job("stale-job-2")])
    workflow_storage.update_job_triage("stale-job-1", "shortlisted")
    workflow_storage.record_event("job_discovered", "Old discovery event")

    async def close_browser():
        return {"success": True}

    monkeypatch.setattr(main, "close_browser_session", close_browser)
    client = TestClient(main.app)

    reset = client.post("/api/data/reset", json={"confirmation": "DELETE ALL LOCAL DATA"})
    assert reset.status_code == 200
    assert reset.json()["counts"]["saved_jobs"] == 0
    assert reset.json()["counts"]["applications"] == 0

    inbox = client.get("/api/workflow/inbox")
    activity = client.get("/api/workflow/activity")
    assert inbox.status_code == 200
    assert inbox.headers["cache-control"].startswith("no-store")
    assert inbox.json()["total"] == 0
    assert inbox.json()["items"] == []
    assert inbox.json()["counts"] == {"new": 0, "reviewing": 0, "shortlisted": 0, "skipped": 0}
    assert activity.status_code == 200
    assert activity.json()["events"] == []
