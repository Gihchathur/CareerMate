"""Regression tests for expanded job coverage and reviewed browser assistance."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.models.job import JobPosting
from app.services import browser_assistance, job_discovery
from app.services.job_sources import arbeitnow, remoteok
from app.services.job_sources.base import JobSourceError


def _job(
    *, source: str, source_id: str, title: str, country: str, location: str,
    work_mode: str = "unknown", description: str = "", url: str | None = None,
) -> JobPosting:
    listing_url = url or f"https://jobs.example.test/{source_id}"
    return JobPosting(
        id=f"{source}:{source_id}", source=source, source_id=source_id,
        title=title, company="Example AB", location=location, description=description,
        published_at="2026-10-01", source_url=listing_url, apply_url=listing_url,
        city="", country=country, work_mode=work_mode, search_roles=[],
    )



def test_arbeitnow_normalizes_jobs_and_preserves_attribution_link() -> None:
    job = arbeitnow.normalize_job({
        "slug": "platform-engineer-berlin-123",
        "company_name": "Example GmbH",
        "title": "Platform Engineer",
        "description": "<p>Kubernetes and observability.</p><p>Find <a href=\"https://www.arbeitnow.com\">Jobs in Germany on Arbeitnow</a></p>",
        "remote": False,
        "url": "https://www.arbeitnow.com/jobs/companies/example/platform-engineer-berlin-123",
        "tags": ["Engineering", "Kubernetes"],
        "job_types": ["Full Time"],
        "location": "Berlin HQ",
        "created_at": 1791567609,
    })

    assert job.source == "arbeitnow"
    assert job.source_id == "platform-engineer-berlin-123"
    assert job.country == "Germany"
    assert job.work_mode == "unknown"
    assert job.source_url.startswith("https://www.arbeitnow.com/jobs/")
    assert job.apply_url == job.source_url
    assert "Kubernetes" in job.description
    assert job.published_at.endswith("+00:00")


def test_arbeitnow_uses_regional_job_page_domain_for_country() -> None:
    job = arbeitnow.normalize_job({
        "slug": "platform-london-100",
        "company_name": "Example UK",
        "title": "Platform Engineer",
        "description": "<p>Build platforms.</p>",
        "remote": True,
        "url": "https://www.arbeitnow.co.uk/jobs/companies/example/platform-london-100",
        "tags": ["Engineering"],
        "job_types": ["Full Time"],
        "location": "Remote - UK",
        "created_at": "2026-10-08T10:00:00Z",
    })
    assert job.country == "United Kingdom"
    assert job.work_mode == "remote"


def test_arbeitnow_caches_results_and_limits_pages(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(arbeitnow, "CACHE_PATH", tmp_path / "arbeitnow.json")
    requests: list[dict[str, object]] = []

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        requests.append(kwargs)
        params = kwargs.get("params")
        page = params.get("page") if isinstance(params, dict) else None
        if page == 1:
            payload = {
                "data": [{
                    "slug": "job-1", "company_name": "Example GmbH", "title": "Platform Engineer",
                    "description": "Build systems", "remote": False,
                    "url": "https://www.arbeitnow.com/jobs/job-1", "location": "Berlin, Germany",
                    "created_at": 1791567609,
                }],
                "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"},
            }
        else:
            payload = {"data": [{
                "slug": "job-2", "company_name": "Example UK", "title": "DevOps Engineer",
                "description": "Remote platform work", "remote": True,
                "url": "https://www.arbeitnow.co.uk/jobs/job-2", "location": "Remote - UK",
                "created_at": 1791567609,
            }], "links": {"next": None}}
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(arbeitnow, "get_with_retries", fake_get)
    first = arbeitnow.fetch_jobs(now=1_800_000_000)
    second = arbeitnow.fetch_jobs(now=1_800_000_100)

    assert [item.source_id for item in first] == ["job-1", "job-2"]
    assert [item.id for item in second] == [item.id for item in first]
    assert len(requests) == 2
    assert (tmp_path / "arbeitnow.json").exists()


def test_search_adds_arbeitnow_roles_and_restricts_country_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    germany = _job(
        source="arbeitnow", source_id="de-role", title="Platform Engineer", country="Germany",
        location="Berlin, Germany", work_mode="hybrid", description="Kubernetes platform team",
        url="https://www.arbeitnow.com/jobs/de-role",
    )
    france = _job(
        source="arbeitnow", source_id="fr-role", title="Platform Engineer", country="France",
        location="Paris, France", work_mode="on_site", description="Platform team",
        url="https://www.arbeitnow.fr/jobs/fr-role",
    )
    remote = _job(
        source="remoteok", source_id="remote-role", title="Platform Engineer", country="Worldwide",
        location="Worldwide", work_mode="remote", description="Kubernetes",
        url="https://remoteok.com/remote-jobs/remote-role",
    )
    monkeypatch.setattr(job_discovery, "fetch_arbeitnow_jobs", lambda: [germany, france])
    monkeypatch.setattr(job_discovery, "fetch_remote_jobs", lambda: [remote])
    monkeypatch.setattr(job_discovery, "search_jobs", lambda **kwargs: (_ for _ in ()).throw(AssertionError("JobTech should be skipped")))

    result = job_discovery.search_multiple_roles(
        roles=["Platform Engineer"], country="France", city="Paris", work_mode="any",
        limit=10, offset=0, sources=["arbeitnow"],
    )
    assert [item.id for item in result["jobs"]] == ["arbeitnow:fr-role"]
    assert result["sources"] == ["arbeitnow"]

    skipped = job_discovery.search_multiple_roles(
        roles=["Platform Engineer"], country="Sweden", city="Stockholm", work_mode="any",
        limit=10, offset=0, sources=["arbeitnow", "remoteok"],
    )
    assert any("Arbeitnow" in warning and "skipped" in warning for warning in skipped["warnings"])
    assert [item.id for item in skipped["jobs"]] == ["remoteok:remote-role"]

def test_remoteok_normalizes_public_feed_and_caches_results(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(remoteok, "CACHE_PATH", tmp_path / "remoteok.json")
    payload = [
        {"legal": "informational metadata"},
        {
            "id": "remote-100", "position": "Platform Engineer", "company": "Example Remote",
            "location": "Worldwide", "url": "https://remoteok.com/remote-jobs/remote-100",
            "apply_url": "https://careers.example.test/jobs/100", "description": "<p>Kubernetes and Linux</p>",
            "tags": ["devops", "kubernetes"], "date": "2026-10-08T10:00:00Z",
        },
    ]

    requests: list[str] = []
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        assert url == remoteok.API_URL
        requests.append(url)
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(remoteok, "get_with_retries", fake_get)
    jobs = remoteok.fetch_remote_jobs(now=1_800_000_000)
    cached_jobs = remoteok.fetch_remote_jobs(now=1_800_000_100)

    assert len(jobs) == 1
    assert len(cached_jobs) == 1
    assert len(requests) == 1
    assert jobs[0].source == "remoteok"
    assert jobs[0].work_mode == "remote"
    assert jobs[0].country == "Worldwide"
    assert jobs[0].source_url == "https://remoteok.com/remote-jobs/remote-100"
    assert jobs[0].apply_url == "https://careers.example.test/jobs/100"
    assert "kubernetes" in jobs[0].description.casefold()


def test_remoteok_bad_payload_is_not_silently_treated_as_empty(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(remoteok, "CACHE_PATH", tmp_path / "remoteok.json")
    monkeypatch.setattr(remoteok, "get_with_retries", lambda *args, **kwargs: httpx.Response(200, json={"jobs": []}, request=httpx.Request("GET", remoteok.API_URL)))
    with pytest.raises(JobSourceError, match="unexpected response format"):
        remoteok.fetch_remote_jobs()


def test_international_search_combines_remote_feed_and_configured_employer_boards(monkeypatch: pytest.MonkeyPatch) -> None:
    remote_worldwide = _job(
        source="remoteok", source_id="worldwide", title="Platform Engineer", country="Worldwide",
        location="Worldwide", work_mode="remote", description="Kubernetes, Terraform",
        url="https://remoteok.com/remote-jobs/worldwide",
    )
    remote_us_only = _job(
        source="remoteok", source_id="us-only", title="Platform Engineer", country="United States",
        location="USA Only", work_mode="remote", description="Platform engineering",
    )
    germany_board = _job(
        source="greenhouse", source_id="de-1", title="Platform Engineer", country="Germany",
        location="Berlin, Germany", work_mode="hybrid", description="Build developer platforms",
    )
    monkeypatch.setattr(job_discovery, "fetch_remote_jobs", lambda: [remote_worldwide, remote_us_only])
    monkeypatch.setattr(job_discovery, "fetch_configured_jobs", lambda selected=None: ([germany_board], [], 1))
    monkeypatch.setattr(job_discovery, "search_jobs", lambda **kwargs: (_ for _ in ()).throw(AssertionError("JobTech must be skipped for Germany")))

    result = job_discovery.search_multiple_roles(
        roles=["Platform Engineer"], country="Germany", city="Berlin", work_mode="any",
        limit=20, offset=0, sources=["jobtech_links", "remoteok", "greenhouse"],
    )

    assert {item.source for item in result["jobs"]} == {"remoteok", "greenhouse"}
    assert {item.id for item in result["jobs"]} == {"remoteok:worldwide", "greenhouse:de-1"}
    assert any("Sweden-focused" in warning for warning in result["warnings"])
    assert result["country"] == "Germany"


def test_international_search_rejects_jobtech_only_with_helpful_message() -> None:
    with pytest.raises(job_discovery.JobDiscoveryError, match="Sweden-focused"):
        job_discovery.search_multiple_roles(
            roles=["Engineer"], country="Norway", city="Oslo", work_mode="any",
            limit=10, offset=0, sources=["jobtech_links"],
        )


def test_browser_assistance_blocks_insecure_or_prohibited_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="HTTPS"):
        browser_assistance.validate_public_https_url("http://example.com/apply")
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="internal"):
        browser_assistance.validate_public_https_url("https://localhost/apply")
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="Private or reserved"):
        browser_assistance.validate_public_https_url("https://127.0.0.1/apply")
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="does not automate LinkedIn"):
        browser_assistance.validate_public_https_url("https://www.linkedin.com/jobs/view/123")

    monkeypatch.setattr(browser_assistance, "_hostname_is_public", lambda host, port: True)
    assert browser_assistance.validate_public_https_url("https://careers.example.org/apply") == "https://careers.example.org/apply"


def test_browser_mapping_suggestions_are_conservative_and_skip_sensitive_fields() -> None:
    assert browser_assistance.suggest_profile_key("First name", "text") == "personal.first_name"
    assert browser_assistance.suggest_profile_key("Email address", "email") == "personal.email"
    assert browser_assistance.suggest_profile_key("Cover letter", "textarea") == "cover_letter"
    assert browser_assistance.suggest_profile_key("Why do you want this role?", "textarea") == "latest_answer"
    assert browser_assistance.suggest_profile_key("One-time verification code", "text") == ""
    assert browser_assistance._field_from_raw({
        "field_id": "cm-field-2", "label": "Password", "kind": "text", "required": True,
    }) is None
    for index, label in enumerate(("Social security number", "Passport number", "Personnummer", "Credit card number", "Date of birth", "DOB", "Birthdate", "Driver license number", "Residence permit number"), start=10):
        assert browser_assistance._field_from_raw({
            "field_id": f"cm-field-{index}", "label": label, "kind": "text", "required": True,
        }) is None
        assert browser_assistance.suggest_profile_key(label, "text") == ""
    assert browser_assistance._field_from_raw({
        "field_id": "field-2", "label": "Email", "kind": "email", "required": True,
    }) is None


def test_browser_fill_request_validates_field_ids_and_count() -> None:
    from app.models.browser_assistance import BrowserFillRequest
    from pydantic import ValidationError

    assert BrowserFillRequest.model_validate({"fields": [{"field_id": "cm-field-1", "value": "hello"}]})
    with pytest.raises(ValidationError):
        BrowserFillRequest.model_validate({"fields": [{"field_id": "submit-button", "value": "yes"}]})
    with pytest.raises(ValidationError):
        BrowserFillRequest.model_validate({"fields": []})


def test_browser_routes_require_user_selected_session_and_never_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    monkeypatch.setattr(main, "load_applications", lambda: [{
        "id": "application:abc", "job_url": "https://careers.example.org/apply", "title": "Engineer",
    }])

    async def fake_open(application_id: str, url: str) -> dict[str, object]:
        return {
            "success": True, "application_id": application_id, "url": url, "title": "Application form",
            "field_count": 1, "fields": [{"field_id": "cm-field-0", "label": "Email", "kind": "email", "required": True, "placeholder": "", "autocomplete": "email", "suggested_key": "personal.email"}],
            "message": "Fields scanned. Review each proposed value before filling; CareerMate will not submit the form.",
        }

    async def fake_fill(application_id: str, fields: list[dict[str, str]]) -> dict[str, object]:
        assert application_id == "application:abc"
        assert fields == [{"field_id": "cm-field-0", "value": "candidate@example.org"}]
        return {"success": True, "filled_count": 1, "skipped": [], "message": "Filled but not submitted."}

    monkeypatch.setattr(main, "open_application_page", fake_open)
    monkeypatch.setattr(main, "fill_reviewed_fields", fake_fill)
    client = TestClient(main.app)

    opened = client.post("/api/applications/application:abc/browser/open")
    assert opened.status_code == 200
    assert opened.json()["field_count"] == 1
    filled = client.post("/api/applications/application:abc/browser/fill", json={
        "fields": [{"field_id": "cm-field-0", "value": "candidate@example.org"}],
    })
    assert filled.status_code == 200
    assert "submit" in filled.json()["message"].casefold()


def test_browser_fill_only_fills_current_scanned_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeLocator:
        def __init__(self, field_id: str, filled: dict[str, str]):
            self.field_id = field_id
            self.filled = filled

        async def count(self) -> int:
            return 1 if self.field_id == "cm-field-0" else 0

        async def is_editable(self) -> bool:
            return True

        async def fill(self, value: str, timeout: int = 5000) -> None:
            self.filled[self.field_id] = value

    class FakePage:
        url = "https://careers.example.org/apply"
        filled: dict[str, str] = {}

        def is_closed(self) -> bool:
            return False

        async def evaluate(self, _script: str) -> list[dict[str, object]]:
            return [{
                "field_id": "cm-field-0", "label": "Email address", "kind": "email",
                "required": True, "placeholder": "you@example.com", "autocomplete": "email",
            }]

        async def title(self) -> str:
            return "Example application"

        def locator(self, selector: str) -> FakeLocator:
            field_id = selector.split('"')[1]
            return FakeLocator(field_id, self.filled)

    page = FakePage()
    session = browser_assistance.ActiveBrowserSession(
        playwright=object(), browser=object(), context=object(), page=page,
        application_id="application:123",
    )
    monkeypatch.setattr(browser_assistance, "_hostname_is_public", lambda host, port: True)
    monkeypatch.setattr(browser_assistance, "_active_session", session)

    result = asyncio.run(browser_assistance.fill_reviewed_fields("application:123", [
        {"field_id": "cm-field-0", "value": "candidate@example.org"},
        {"field_id": "cm-field-4", "value": "must not be filled"},
        {"field_id": "cm-field-1", "value": ""},
    ]))

    assert page.filled == {"cm-field-0": "candidate@example.org"}
    assert result["filled_count"] == 1
    assert len(result["skipped"]) == 2
    assert "did not submit" in result["message"].casefold()


def test_public_only_search_does_not_require_optional_employer_board_config(monkeypatch: pytest.MonkeyPatch) -> None:
    remote_worldwide = _job(
        source="remoteok", source_id="worldwide", title="Platform Engineer", country="Worldwide",
        location="Worldwide", work_mode="remote", description="Kubernetes",
    )
    monkeypatch.setattr(job_discovery, "fetch_remote_jobs", lambda: [remote_worldwide])

    def optional_boards_must_not_be_read(_selected: object = None) -> object:
        raise AssertionError("Optional ATS configuration should not load when no ATS source was selected")

    monkeypatch.setattr(job_discovery, "fetch_configured_jobs", optional_boards_must_not_be_read)
    result = job_discovery.search_multiple_roles(
        roles=["Platform Engineer"], country="Any country", city="", work_mode="remote",
        limit=10, offset=0, sources=["remoteok"],
    )
    assert [item.source for item in result["jobs"]] == ["remoteok"]


def test_public_api_health_and_source_status_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    monkeypatch.setattr(main, "source_status", lambda: {
        "jobtech_links": {"configured": True, "employers": None, "requires_api_key": False},
        "remoteok": {"configured": True, "employers": None, "requires_api_key": False},
        "greenhouse": {"configured": False, "employers": 0, "requires_api_key": False},
        "lever": {"configured": False, "employers": 0, "requires_api_key": False},
        "teamtailor": {"configured": False, "employers": 0, "requires_api_key": True, "credentials_ready": False, "missing_credentials": 0},
    })
    client = TestClient(main.app)
    health = client.get("/api/health")
    sources = client.get("/api/jobs/sources")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert sources.status_code == 200
    assert sources.json()["sources"]["remoteok"]["configured"] is True
