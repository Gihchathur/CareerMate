import json
from types import SimpleNamespace

from app.models.candidate import CandidateProfile
from app.services import job_matcher
from app.services.job_matcher import score_job
from app.services.job_sources.jobtech_links import normalize_job
from app.services import job_storage


def test_candidate_profile_uses_explicit_personal_fields() -> None:
    profile = CandidateProfile.model_validate(
        {
            "personal": {
                "name": "Example Candidate",
                "email": "candidate@example.com",
                "additionalProp1": "discard this schema placeholder",
            },
            "skills": ["Writing", "Research"],
        }
    )
    assert profile.personal.name == "Example Candidate"
    assert profile.personal.email == "candidate@example.com"
    assert not hasattr(profile.personal, "additionalProp1")
    assert profile.skills == ["Writing", "Research"]


def test_jobtech_normalize_job_maps_public_result() -> None:
    job = normalize_job(
        {
            "id": "12345",
            "headline": "Operations Coordinator",
            "employer": {"name": "Example AB"},
            "workplace_address": {
                "municipality": {"name": "Stockholm"},
                "region": {"name": "Stockholm County"},
            },
            "brief": "Coordinate day-to-day operations.",
            "publication_date": "2026-10-01",
            "source_links": [{"url": "https://example.com/jobs/1"}],
        }
    )
    assert job.id == "jobtech-links:12345"
    assert job.title == "Operations Coordinator"
    assert job.company == "Example AB"
    assert job.location == "Stockholm, Stockholm County"
    assert job.apply_url == "https://example.com/jobs/1"


def test_jobtech_rejects_non_http_source_url() -> None:
    job = normalize_job(
        {
            "id": "unsafe",
            "headline": "Example Role",
            "source_links": [{"url": "javascript:alert(1)"}],
        }
    )
    assert job.source_url == ""
    assert job.apply_url == ""


def test_job_storage_deduplicates_repeat_source_ids(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(job_storage, "JOBS_PATH", tmp_path / "jobs.json")
    job = {
        "id": "jobtech-links:123",
        "source": "jobtech_links",
        "source_id": "123",
        "title": "Example Role",
        "company": "Example AB",
        "location": "Stockholm",
        "description": "",
        "published_at": "",
        "source_url": "https://example.com/jobs/123",
        "apply_url": "https://example.com/jobs/123",
    }
    assert job_storage.save_jobs([job]) == 1
    assert job_storage.save_jobs([{**job, "description": "Updated description"}]) == 1
    stored = job_storage.load_saved_jobs()
    assert len(stored) == 1
    assert stored[0]["description"] == "Updated description"


def test_matching_validates_evidence_and_excludes_contact_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    requirements = [
        {
            "requirement": "Written communication",
            "category": "skill",
            "importance": "required",
            "status": "supported",
            "evidence": "Prepared written reports for stakeholders.",
            "explanation": "The profile directly mentions this.",
        },
        {
            "requirement": "Professional certification",
            "category": "certification",
            "importance": "required",
            "status": "not_evidenced",
            "evidence": "",
            "explanation": "No certification was listed.",
        },
    ]
    model_content = json.dumps({
        "requirements": requirements,
        "summary": "The profile supports one requirement; one is not evidenced.",
    })
    captured: dict[str, str] = {}

    class FakeClient:
        def __init__(self, host: str):
            captured["host"] = host

        def chat(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return SimpleNamespace(
                message=SimpleNamespace(content=model_content),
            )

    monkeypatch.setattr(job_matcher, "Client", FakeClient)

    job = {
        "id": "example:1",
        "title": "Operations Coordinator",
        "company": "Example AB",
        "location": "Stockholm",
        "description": "This is a long enough job description for the test.",
    }
    profile = {
        "personal": {
            "name": "Private Example",
            "email": "secret@example.com",
        },
        "summary": "Prepared written reports for stakeholders.",
        "skills": ["Written communication"],
        "experience": [],
        "education": [],
        "certifications": [],
        "languages": [],
    }

    result = score_job(job, profile)

    assert result["match_score"] == 50
    assert result["matched_requirements"] == ["Written communication"]
    assert result["missing_requirements"] == ["Professional certification"]
    assert "secret@example.com" not in captured["prompt"]
    assert (tmp_path / "match_cache.json").exists()


def test_matches_endpoint_honors_selected_ids_and_limit(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from app import main

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        CandidateProfile.model_validate({}).model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    jobs = [
        {"id": "job-1", "title": "First", "company": "A", "location": "X"},
        {"id": "job-2", "title": "Second", "company": "B", "location": "Y"},
    ]
    monkeypatch.setattr(main, "load_saved_jobs", lambda: jobs)
    analyzed: list[str] = []

    def fake_score(job, _profile):
        analyzed.append(job["id"])
        return {
            "match_score": 50,
            "match_confidence": "low",
            "match_method": "test",
            "matched_skills": [],
            "matched_requirements": [],
            "partially_matched_requirements": [],
            "missing_requirements": [],
            "requirements": [],
            "match_explanation": "test result",
            "score_note": "test only",
        }

    monkeypatch.setattr(main, "score_job", fake_score)
    response = TestClient(main.app).get(
        "/api/jobs/matches?limit=1&job_ids=job-2&job_ids=job-1"
    )

    assert response.status_code == 200
    assert analyzed == ["job-2"]
    assert response.json()["analyzed"] == 1
    assert response.json()["jobs"][0]["id"] == "job-2"
