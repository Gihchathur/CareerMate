import json
import sys
import types

from fastapi.testclient import TestClient

from app import main
from app.models.application import ApplicationRecord
from app.models.candidate import CandidateProfile
from app.services import application_drafts, application_storage


JOB = {
    "id": "jobtech-links:application-test-1",
    "source": "jobtech_links",
    "source_id": "application-test-1",
    "title": "Platform Engineer",
    "company": "Example AB",
    "location": "Stockholm, Sweden",
    "description": "Operate Kubernetes services, maintain CI/CD pipelines, and improve observability.",
    "published_at": "2026-10-01",
    "source_url": "https://example.com/jobs/platform-engineer",
    "apply_url": "https://example.com/jobs/platform-engineer/apply",
}


LONG_COVER_LETTER = "Dear hiring team,\n\nI am interested in the Platform Engineer role because the responsibilities align with my background in software engineering and production operations. My work has involved building and maintaining backend services and working with tools that support reliable delivery. These experiences have helped me understand how implementation choices affect operability, quality, and the people who use a system.\n\nIn my professional experience, I have worked with Kubernetes, CI/CD pipelines, and observability tools to support production services. I have contributed to automation and monitoring approaches that help teams understand system behaviour, identify problems, and make releases more predictable. I bring a practical perspective on the connection between development, deployment, and service reliability.\n\nI would bring these skills to the role while continuing to build depth in areas specific to your product and engineering environment. I am comfortable learning the context of an existing system, understanding why a change is needed, and choosing a maintainable way to deliver it. I would also be careful to communicate what is known, where risks remain, and what needs to be verified before a change is released.\n\nThe opportunity to contribute to useful software and help improve its long-term quality is appealing in the context of the role described. I would welcome a conversation about the team's current priorities and where my experience could be most useful.\n\nKind regards,\nExample Candidate"


def test_create_application_is_idempotent_and_stores_job_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", tmp_path / "applications.json")
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])
    client = TestClient(main.app)

    first = client.post("/api/applications", json={"job_id": JOB["id"]})
    second = client.post("/api/applications", json={"job_id": JOB["id"]})

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert first.json()["application"]["job_description"] == JOB["description"]
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["application"]["id"] == first.json()["application"]["id"]
    saved = json.loads((tmp_path / "applications.json").read_text(encoding="utf-8"))
    assert len(saved) == 1


def test_create_application_requires_existing_saved_job(tmp_path, monkeypatch):
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", tmp_path / "applications.json")
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [])

    response = TestClient(main.app).post("/api/applications", json={"job_id": "missing-job"})
    assert response.status_code == 404
    assert "not in your saved jobs" in response.json()["detail"]


def test_update_application_persists_status_notes_and_follow_up(tmp_path, monkeypatch):
    app_path = tmp_path / "applications.json"
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", app_path)
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    response = client.put(
        f"/api/applications/{created['id']}",
        json={
            "status": "applied",
            "notes": "Sent the reviewed application.",
            "follow_up_date": "2026-10-20",
            "cover_letter": "Dear hiring team, ...",
            "answers": [{"question": "Why this role?", "answer": "My reviewed answer."}],
        },
    )

    assert response.status_code == 200
    record = response.json()["application"]
    assert record["status"] == "applied"
    assert record["notes"] == "Sent the reviewed application."
    assert record["follow_up_date"] == "2026-10-20"
    assert record["applied_at"]
    assert record["answers"][0]["answer"] == "My reviewed answer."
    persisted = json.loads(app_path.read_text(encoding="utf-8"))[0]
    assert persisted["status"] == "applied"


def test_invalid_application_status_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", tmp_path / "applications.json")
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    response = client.put(f"/api/applications/{created['id']}", json={"status": "maybe"})
    assert response.status_code == 422


def test_cover_letter_draft_requires_saved_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", tmp_path / "applications.json")
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])
    monkeypatch.setattr(main, "PROFILE_PATH", tmp_path / "missing-profile.json")
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    response = client.post(f"/api/applications/{created['id']}/draft-cover-letter")
    assert response.status_code == 400
    assert "save your CV profile" in response.json()["detail"]


def test_local_cover_letter_prompt_excludes_contact_details(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, host: str):
            captured["host"] = host

        def chat(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return types.SimpleNamespace(message=types.SimpleNamespace(content=LONG_COVER_LETTER))

    monkeypatch.setitem(sys.modules, "ollama", types.SimpleNamespace(Client=FakeClient))
    profile = CandidateProfile.model_validate({
        "personal": {"name": "Example Candidate", "email": "private@example.com", "phone": "+460000000"},
        "summary": "Worked with Kubernetes and CI/CD systems.",
        "skills": ["Kubernetes", "CI/CD"],
    })
    application = ApplicationRecord(
        id="application:test",
        job_id=JOB["id"],
        company=JOB["company"],
        title=JOB["title"],
        location=JOB["location"],
        source=JOB["source"],
        job_url=JOB["apply_url"],
        job_description=JOB["description"],
    )

    result = application_drafts.generate_cover_letter(application, profile)
    assert result.startswith("Dear hiring team")
    assert "private@example.com" not in captured["prompt"]
    assert "+460000000" not in captured["prompt"]
    assert "Never invent employers" in captured["prompt"]
    assert "Sanitized text extracted from the candidate's current CV" in captured["prompt"]
    assert len(result.split()) >= 200


def test_cover_letter_endpoint_persists_local_draft(tmp_path, monkeypatch):
    app_path = tmp_path / "applications.json"
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", app_path)
    full_job = {**JOB, "description": ("Operate Kubernetes services, maintain CI/CD pipelines, improve observability, and collaborate with engineers to support production systems. " * 8), "description_source": "original_listing"}
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [full_job])
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    profile_path.write_text(CandidateProfile.model_validate({"summary": "Kubernetes operations"}).model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(main, "_refresh_application_description", lambda application, force=False: application)
    monkeypatch.setattr(main, "generate_cover_letter", lambda _application, _profile: "A reviewed cover-letter draft.")
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    response = client.post(f"/api/applications/{created['id']}/draft-cover-letter")

    assert response.status_code == 200
    assert response.json()["application"]["cover_letter"] == "A reviewed cover-letter draft."
    assert json.loads(app_path.read_text(encoding="utf-8"))[0]["cover_letter"] == "A reviewed cover-letter draft."


def test_application_question_answer_is_saved_and_same_question_is_replaced(tmp_path, monkeypatch):
    app_path = tmp_path / "applications.json"
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", app_path)
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    profile_path.write_text(CandidateProfile.model_validate({"summary": "Kubernetes operations"}).model_dump_json(), encoding="utf-8")
    generated = iter(["First draft.", "Improved second draft."])
    monkeypatch.setattr(main, "_refresh_application_description", lambda application, force=False: application)
    monkeypatch.setattr(main, "generate_application_answer", lambda _application, _profile, _question: next(generated))
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    first = client.post(f"/api/applications/{created['id']}/draft-answer", json={"question": "Why this role?"})
    second = client.post(f"/api/applications/{created['id']}/draft-answer", json={"question": "Why this role?"})

    assert first.status_code == 200 and second.status_code == 200
    answers = second.json()["application"]["answers"]
    assert len(answers) == 1
    assert answers[0]["answer"] == "Improved second draft."


def test_confirmed_browser_submission_persists_submitted_details_for_offer_follow_up(tmp_path, monkeypatch):
    app_path = tmp_path / "applications.json"
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", app_path)
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [JOB])

    async def fake_submit(application_id, confirmation, expected_url=None):
        assert confirmation is True
        assert application_id
        assert expected_url == "https://example.com/jobs/platform-engineer/apply"
        return {
            "success": True,
            "clicked": True,
            "confirmation_detected": True,
            "message": "Thanks for applying.",
            "url": expected_url,
            "title": "Application received",
        }

    monkeypatch.setattr(main, "submit_reviewed_application", fake_submit)
    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": JOB["id"]}).json()["application"]

    submitted = [{"question": "Application step: Why this role?", "answer": "My reviewed answer.", "updated_at": "2026-10-19T10:00:00Z"}]
    response = client.post(
        f"/api/applications/{created['id']}/browser/submit",
        json={
            "confirm_submission": True,
            "expected_url": JOB["apply_url"],
            "submitted_details": submitted,
        },
    )

    assert response.status_code == 200
    record = json.loads(app_path.read_text(encoding="utf-8"))[0]
    assert record["status"] == "applied"
    assert record["applied_at"]
    assert record["submitted_details"][0]["question"] == submitted[0]["question"]
    assert record["submitted_details"][0]["answer"] == "My reviewed answer."

    # The saved application can progress to an offer without losing the submission snapshot.
    updated = client.put(f"/api/applications/{created['id']}", json={"status": "offer"})
    assert updated.status_code == 200
    assert updated.json()["application"]["status"] == "offer"
    assert updated.json()["application"]["submitted_details"][0]["answer"] == "My reviewed answer."
