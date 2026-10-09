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


def test_jobtech_extracts_work_mode_only_from_explicit_evidence() -> None:
    remote = normalize_job({
        "id": "remote-1",
        "headline": "Customer Support Specialist",
        "brief": "Fully remote position with flexible hours.",
    })
    hybrid = normalize_job({
        "id": "hybrid-1",
        "headline": "Accountant",
        "brief": "This is a hybrid role with office and home days.",
    })
    unknown = normalize_job({
        "id": "unknown-1",
        "headline": "Registered Nurse",
        "brief": "Work as part of a supportive care team.",
    })

    assert remote.work_mode == "remote"
    assert hybrid.work_mode == "hybrid"
    assert unknown.work_mode == "unknown"


def test_multi_role_search_deduplicates_and_keeps_search_roles(monkeypatch) -> None:
    from app.models.job import JobPosting
    from app.services import job_discovery

    shared = JobPosting(
        id="jobtech-links:shared", source="jobtech_links", source_id="shared",
        title="Project Coordinator", company="Example AB", location="Stockholm",
        description="Coordinate projects.", published_at="2026-10-01",
        source_url="https://example.com/jobs/shared", apply_url="https://example.com/jobs/shared",
    )
    only_a = JobPosting(
        id="jobtech-links:a", source="jobtech_links", source_id="a",
        title="Operations Coordinator", company="A AB", location="Stockholm",
        description="Coordinate operations.", published_at="2026-10-02",
        source_url="https://example.com/jobs/a", apply_url="https://example.com/jobs/a",
    )
    only_b = JobPosting(
        id="jobtech-links:b", source="jobtech_links", source_id="b",
        title="Project Assistant", company="B AB", location="Stockholm",
        description="Support project work.", published_at="2026-10-03",
        source_url="https://example.com/jobs/b", apply_url="https://example.com/jobs/b",
    )
    calls: list[str] = []

    def fake_search(query: str, limit: int, offset: int):
        calls.append(query)
        if query.startswith("Project Coordinator"):
            return 30, [shared.model_copy(), only_a]
        return 20, [shared.model_copy(), only_b]

    monkeypatch.setattr(job_discovery, "search_jobs", fake_search)
    result = job_discovery.search_multiple_roles(
        roles=["Project Coordinator", "Operations Coordinator"],
        country="Sweden",
        city="Stockholm",
        work_mode="any",
        limit=10,
        offset=0,
    )

    assert calls == ["Project Coordinator Stockholm", "Operations Coordinator Stockholm"]
    assert result["returned"] == 3
    jobs = result["jobs"]
    assert len(jobs) == 3
    shared_result = next(job for job in jobs if job.id == "jobtech-links:shared")
    assert shared_result.search_roles == ["Project Coordinator", "Operations Coordinator"]
    assert result["total_reported"] == 50
    assert result["total_is_approximate"] is True


def test_multi_role_search_filters_unknown_work_mode_and_rejects_unsupported_country(monkeypatch) -> None:
    from app.models.job import JobPosting
    from app.services import job_discovery

    remote = JobPosting(
        id="jobtech-links:remote", source="jobtech_links", source_id="remote",
        title="Remote Researcher", company="Research AB", location="Sweden",
        description="Fully remote role.", published_at="2026-10-02",
        source_url="https://example.com/jobs/remote", apply_url="https://example.com/jobs/remote",
        work_mode="remote",
    )
    unknown = JobPosting(
        id="jobtech-links:unknown", source="jobtech_links", source_id="unknown",
        title="Researcher", company="Research AB", location="Sweden",
        description="Research and report.", published_at="2026-10-01",
        source_url="https://example.com/jobs/unknown", apply_url="https://example.com/jobs/unknown",
        work_mode="unknown",
    )
    monkeypatch.setattr(job_discovery, "search_jobs", lambda **kwargs: (40, [remote, unknown]))

    result = job_discovery.search_multiple_roles(
        roles=["Researcher"], country="Sweden", city="", work_mode="remote", limit=10, offset=0,
    )
    assert [job.id for job in result["jobs"]] == ["jobtech-links:remote"]
    assert result["filtered_out"] == 1

    try:
        job_discovery.search_multiple_roles(
            roles=["Researcher"], country="Germany", city="", work_mode="any", limit=10, offset=0,
        )
    except job_discovery.JobDiscoveryError as exc:
        assert "configured for Sweden" in str(exc)
    else:
        raise AssertionError("Unsupported country should be rejected clearly")


def test_load_saved_jobs_treats_blank_file_as_empty(tmp_path, monkeypatch) -> None:
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text("   \n", encoding="utf-8")
    monkeypatch.setattr(job_storage, "JOBS_PATH", jobs_path)

    assert job_storage.load_saved_jobs() == []


def test_job_search_endpoint_passes_multiple_roles_and_saves_results(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from app import main
    from app.models.job import JobPosting

    job = JobPosting(
        id="jobtech-links:sample", source="jobtech_links", source_id="sample",
        title="Project Coordinator", company="Example AB", location="Stockholm",
        description="Coordinate projects.", published_at="2026-10-01",
        source_url="https://example.com/jobs/sample", apply_url="https://example.com/jobs/sample",
        search_roles=["Project Coordinator"],
    )
    observed: dict[str, object] = {}

    def fake_discovery(**kwargs):
        observed.update(kwargs)
        return {
            "roles": ["Project Coordinator", "Operations Coordinator"],
            "country": "Sweden",
            "city": "Stockholm",
            "work_mode": "any",
            "total_reported": 10,
            "total_is_approximate": True,
            "offset": 0,
            "limit": 10,
            "returned": 1,
            "has_more": True,
            "filtered_out": 0,
            "role_searches": 2,
            "warnings": [],
            "filter_note": "test note",
            "jobs": [job],
        }

    monkeypatch.setattr(main, "search_multiple_roles", fake_discovery)
    monkeypatch.setattr(main, "save_jobs", lambda jobs: 1)

    response = TestClient(main.app).get(
        "/api/jobs/search?roles=Project%20Coordinator&roles=Operations%20Coordinator&sources=jobtech_links&sources=greenhouse&country=Sweden&city=Stockholm&work_mode=any&limit=10&offset=0"
    )

    assert response.status_code == 200
    assert observed["roles"] == ["Project Coordinator", "Operations Coordinator"]
    assert observed["sources"] == ["jobtech_links", "greenhouse"]
    assert response.json()["jobs"][0]["id"] == "jobtech-links:sample"
    assert response.json()["saved_total"] == 1


def test_job_search_endpoint_rejects_country_not_yet_supported() -> None:
    from fastapi.testclient import TestClient
    from app import main

    response = TestClient(main.app).get(
        "/api/jobs/search?roles=Analyst&country=Germany"
    )

    assert response.status_code == 400
    assert "configured for Sweden" in response.json()["detail"]


# Step 10: company-specific ATS source adapters.
def test_greenhouse_adapter_normalizes_public_board_job() -> None:
    from app.services.job_sources.greenhouse import normalize_job

    job = normalize_job(
        {
            "id": 123,
            "title": "Platform Engineer",
            "updated_at": "2026-10-01T12:00:00Z",
            "location": {"name": "Stockholm, Sweden"},
            "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
            "content": "<h2>What you will do</h2><p>Operate Kubernetes platforms.</p>",
        },
        board_token="example-board",
        company_name="Example AB",
    )

    assert job.source == "greenhouse"
    assert job.source_id == "example-board:123"
    assert job.company == "Example AB"
    assert job.country == "Sweden"
    assert "Operate Kubernetes platforms" in job.description
    assert job.apply_url == "https://boards.greenhouse.io/example/jobs/123"


def test_lever_adapter_uses_workplace_type_and_normalizes_location() -> None:
    from app.services.job_sources.lever import normalize_job

    job = normalize_job(
        {
            "id": "posting-abc",
            "text": "Data Engineer",
            "categories": {"location": "Stockholm, Sweden", "team": "Data"},
            "country": "SE",
            "workplaceType": "hybrid",
            "descriptionPlain": "Build data pipelines.",
            "hostedUrl": "https://jobs.eu.lever.co/example/posting-abc",
            "applyUrl": "https://jobs.eu.lever.co/example/posting-abc/apply",
        },
        site="example",
        company_name="Example AB",
    )

    assert job.source == "lever"
    assert job.title == "Data Engineer"
    assert job.country == "Sweden"
    assert job.work_mode == "hybrid"
    assert job.apply_url.endswith("/apply")


def test_teamtailor_adapter_uses_career_site_links_and_public_work_mode() -> None:
    from app.services.job_sources.teamtailor import normalize_job

    job = normalize_job(
        {
            "id": "job-42",
            "links": {
                "careersite-job-url": "https://example.teamtailor.com/jobs/42-engineer",
                "careersite-job-apply-url": "https://example.teamtailor.com/jobs/42-engineer/applications/new",
            },
            "attributes": {
                "title": "Software Engineer",
                "body": "<p>Build systems.</p>",
                "pitch": "Work in a hybrid team.",
                "human-status": "published",
                "remote-status": "hybrid",
            },
            "_careermate_locations": ["Stockholm, Sweden"],
        },
        company_name="Example AB",
    )

    assert job.source == "teamtailor"
    assert job.location == "Stockholm, Sweden"
    assert job.country == "Sweden"
    assert job.work_mode == "hybrid"
    assert "Work in a hybrid team" in job.description
    assert job.source_url.endswith("42-engineer")


def test_configured_employer_board_jobs_are_filtered_and_merged(monkeypatch) -> None:
    from app.models.job import JobPosting
    from app.services import job_discovery

    public_job = JobPosting(
        id="jobtech-links:public", source="jobtech_links", source_id="public",
        title="Cloud Engineer", company="JobTech AB", location="Stockholm, Sweden",
        description="Cloud infrastructure.", published_at="2026-10-01",
        source_url="https://jobs.example.org/public", apply_url="https://jobs.example.org/public",
        country="Sweden", search_roles=[],
    )
    greenhouse_job = JobPosting(
        id="greenhouse:acme:1", source="greenhouse", source_id="acme:1",
        title="Cloud Engineer", company="Acme AB", location="Stockholm, Sweden",
        description="Build cloud systems.", published_at="2026-10-02",
        source_url="https://boards.greenhouse.io/acme/jobs/1", apply_url="https://boards.greenhouse.io/acme/jobs/1",
        country="Sweden",
    )
    unrelated_job = JobPosting(
        id="greenhouse:acme:2", source="greenhouse", source_id="acme:2",
        title="Data Analyst", company="Acme AB", location="Stockholm, Sweden",
        description="Analyze data.", published_at="2026-10-02",
        source_url="https://boards.greenhouse.io/acme/jobs/2", apply_url="https://boards.greenhouse.io/acme/jobs/2",
        country="Sweden",
    )
    monkeypatch.setattr(job_discovery, "search_jobs", lambda **kwargs: (1, [public_job.model_copy()]))
    monkeypatch.setattr(job_discovery, "fetch_configured_jobs", lambda _sources=None: ([greenhouse_job, unrelated_job], [], 1))

    result = job_discovery.search_multiple_roles(
        roles=["Cloud Engineer"], country="Sweden", city="Stockholm", work_mode="any", limit=10, offset=0,
    )

    assert {job.source for job in result["jobs"]} == {"jobtech_links", "greenhouse"}
    assert len(result["jobs"]) == 2
    assert all("Cloud Engineer" in job.search_roles for job in result["jobs"])
    assert result["configured_employer_boards"] == 1


def test_source_status_reports_counts_without_credentials(tmp_path, monkeypatch) -> None:
    from app.services import job_search

    path = tmp_path / "sources.json"
    path.write_text(
        '{"greenhouse": [], "lever": [], "teamtailor": [{"enabled": true, "company": "Example AB", "api_key_env": "SECRET_NAME"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(job_search, "SOURCE_CONFIG_PATH", path)

    status = job_search.source_status()
    assert status["teamtailor"]["configured"] is True
    assert status["teamtailor"]["employers"] == 1
    assert status["teamtailor"]["credentials_ready"] is False
    assert "SECRET_NAME" not in str(status)



def test_search_only_calls_selected_source_adapters(monkeypatch) -> None:
    from app.models.job import JobPosting
    from app.services import job_discovery

    greenhouse_job = JobPosting(
        id="greenhouse:acme:7", source="greenhouse", source_id="acme:7",
        title="Cloud Engineer", company="Acme AB", location="Stockholm, Sweden",
        description="Build cloud systems.", published_at="2026-10-02",
        source_url="https://boards.greenhouse.io/acme/jobs/7", apply_url="https://boards.greenhouse.io/acme/jobs/7",
        country="Sweden",
    )
    called: list[str] = []

    def fake_fetch(selected_sources=None):
        called.extend(selected_sources or [])
        return [greenhouse_job], [], 1

    def fail_if_jobtech_called(**kwargs):
        raise AssertionError("JobTech must not be called when the user deselects it.")

    monkeypatch.setattr(job_discovery, "fetch_configured_jobs", fake_fetch)
    monkeypatch.setattr(job_discovery, "search_jobs", fail_if_jobtech_called)
    result = job_discovery.search_multiple_roles(
        roles=["Cloud Engineer"], country="Sweden", city="Stockholm", work_mode="any",
        limit=10, offset=0, sources=["greenhouse"],
    )

    assert called == ["greenhouse"]
    assert result["sources"] == ["greenhouse"]
    assert [job.source for job in result["jobs"]] == ["greenhouse"]



def test_search_rejects_unknown_source_identifier() -> None:
    from app.services import job_discovery

    try:
        job_discovery.search_multiple_roles(
            roles=["Engineer"], country="Sweden", city="", work_mode="any",
            limit=10, offset=0, sources=["unknown-provider"],
        )
    except job_discovery.JobDiscoveryError as exc:
        assert "Unsupported job source" in str(exc)
    else:
        raise AssertionError("Unknown source IDs should be rejected clearly")
