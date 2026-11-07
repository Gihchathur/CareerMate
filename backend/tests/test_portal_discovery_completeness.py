from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.job import JobPosting
from app.services import job_discovery
from app.services.job_sources import lever, public_ats, teamtailor
from app.services.job_sources.base import JobSourceError, JobSourceStaleCacheError


def make_job(**overrides) -> JobPosting:
    payload = {
        "id": "ashby:legora:1",
        "source": "ashby",
        "source_id": "legora:1",
        "portal_id": "ashby:legora",
        "portal_name": "Legora",
        "title": "AI Software Engineer",
        "company": "Legora",
        "location": "Stockholm HQ",
        "description": "Build software.",
        "published_at": "2026-11-01T10:00:00Z",
        "source_url": "https://jobs.ashbyhq.com/legora/1",
        "apply_url": "https://jobs.ashbyhq.com/legora/1",
        "city": "Stockholm",
        "country": "Sweden",
        "work_mode": "on_site",
        "source_fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return JobPosting(**payload)


def test_ashby_legora_reads_all_public_listings_and_normalizes_iso_country(monkeypatch):
    rows = [
        {
            "id": "ai-software",
            "title": "AI Software Engineer",
            "location": "Stockholm HQ",
            "address": {"postalAddress": {"addressLocality": "Stockholm", "addressCountry": "SE"}},
            "department": "Engineering",
            "team": "Platform",
            "employmentType": "FullTime",
            "isListed": True,
            "isRemote": False,
            "workplaceType": "OnSite",
            "jobUrl": "https://jobs.ashbyhq.com/legora/ai-software",
            "descriptionPlain": "Build AI systems.",
        },
        {
            "id": "consultant",
            "title": "Business Value Consultant",
            "location": "New York City",
            "address": {"postalAddress": {"addressLocality": "New York City", "addressCountry": "US"}},
            "isListed": True,
            "workplaceType": "Hybrid",
            "isRemote": True,
            "jobUrl": "https://jobs.ashbyhq.com/legora/consultant",
            "descriptionPlain": "Partner with the software engineering team.",
        },
        {
            "id": "not-listed",
            "title": "Hidden Software Engineer",
            "location": "Stockholm HQ",
            "isListed": False,
        },
    ]
    monkeypatch.setattr(public_ats, "_get_json", lambda *args, **kwargs: {"jobs": rows})

    jobs = public_ats._fetch_public_board_uncached(
        "ashby", {"slug": "legora", "company": "Legora", "country": "Sweden"}
    )

    assert len(jobs) == 2
    engineer = next(job for job in jobs if job.source_id == "legora:ai-software")
    assert engineer.portal_id == "ashby:legora"
    assert engineer.city == "Stockholm"
    assert engineer.country == "Sweden"
    assert engineer.department == "Engineering"
    assert engineer.team == "Platform"
    assert engineer.source_fetched_at
    consultant = next(job for job in jobs if job.source_id == "legora:consultant")
    assert consultant.work_mode == "hybrid"


def test_role_matching_uses_title_not_description_or_department():
    irrelevant = make_job(
        title="Business Value Consultant",
        description="Collaborate with software engineers and platform teams.",
        department="Software Engineering",
    )
    relevant = make_job(title="Senior Software Engineer, Platform")
    ai_relevant = make_job(title="AI Software Engineer")
    engineering_manager = make_job(title="Software Engineering Manager")

    assert not job_discovery._role_matches("Software Engineer", irrelevant)
    assert not job_discovery._role_matches("Software Engineer", engineering_manager)
    assert job_discovery._role_matches("Software Engineer", relevant)
    assert job_discovery._role_matches("Software Engineer", ai_relevant)


def test_legora_search_reports_retrieval_vs_role_and_location_filter_counts(monkeypatch):
    jobs = [
        make_job(id="1", source_id="legora:1", title="AI Software Engineer", source_url="https://jobs.ashbyhq.com/legora/ai", apply_url="https://jobs.ashbyhq.com/legora/ai"),
        make_job(id="2", source_id="legora:2", title="Senior Software Engineer", source_url="https://jobs.ashbyhq.com/legora/senior", apply_url="https://jobs.ashbyhq.com/legora/senior"),
        make_job(
            id="3", source_id="legora:3", title="Business Value Consultant",
            location="New York City", city="New York City", country="United States",
            description="Work with the software engineering team.",
            source_url="https://jobs.ashbyhq.com/legora/consultant",
            apply_url="https://jobs.ashbyhq.com/legora/consultant",
        ),
    ]
    monkeypatch.setattr(job_discovery, "fetch_configured_jobs", lambda *args, **kwargs: (jobs, [], 1))
    monkeypatch.setattr(
        job_discovery,
        "list_configured_portals",
        lambda *args, **kwargs: [{"id": "ashby:legora", "provider": "ashby", "company": "Legora"}],
    )

    result = job_discovery.search_multiple_roles(
        roles=["Software Engineer"],
        country="Sweden",
        city="Stockholm",
        work_mode="any",
        limit=20,
        offset=0,
        sources=["ashby"],
        portal_ids=["ashby:legora"],
    )

    assert {job.title for job in result["jobs"]} == {"AI Software Engineer", "Senior Software Engineer"}
    coverage = result["portal_results"][0]
    assert coverage["fetched_count"] == 3
    assert coverage["role_matches"] == 2
    assert coverage["eligible_matches"] == 2
    assert coverage["status"] == "matched"
    assert len(result["all_jobs"]) == 2

    next_page = job_discovery.search_multiple_roles(
        roles=["Software Engineer"],
        country="Sweden",
        city="Stockholm",
        work_mode="any",
        limit=1,
        offset=1,
        sources=["ashby"],
        portal_ids=["ashby:legora"],
    )
    assert len(next_page["jobs"]) == 1
    assert len(next_page["all_jobs"]) == 2


def test_smartrecruiters_paginates_beyond_previous_500_job_cap(monkeypatch):
    total = 625
    requests = []

    def fake_get_json(url, params=None):
        offset = int(params["offset"])
        limit = int(params["limit"])
        requests.append(offset)
        count = min(limit, total - offset)
        return {
            "totalFound": total,
            "content": [
                {
                    "id": f"sr-{offset + index}",
                    "name": f"Software Engineer {offset + index}",
                    "location": {"city": "Stockholm", "country": "Sweden", "fullLocation": "Stockholm, Sweden"},
                    "ref": f"https://jobs.smartrecruiters.com/example/{offset + index}",
                }
                for index in range(count)
            ],
        }

    monkeypatch.setattr(public_ats, "_get_json", fake_get_json)
    jobs = public_ats._fetch_public_board_uncached(
        "smartrecruiters", {"slug": "example", "company": "Example", "country": "Sweden"}
    )

    assert len(jobs) == total
    assert requests == [0, 100, 200, 300, 400, 500, 600]


def test_workday_paginates_beyond_previous_400_job_cap(monkeypatch):
    total = 425
    requests = []

    def fake_post_json(url, payload):
        offset = int(payload["offset"])
        limit = int(payload["limit"])
        requests.append(offset)
        count = min(limit, total - offset)
        return {
            "total": total,
            "jobPostings": [
                {
                    "jobReqId": f"wd-{offset + index}",
                    "title": f"Software Engineer {offset + index}",
                    "locationsText": "Stockholm, Sweden",
                    "externalPath": f"/job/Stockholm/Engineer_{offset + index}",
                }
                for index in range(count)
            ],
        }

    monkeypatch.setattr(public_ats, "_post_json", fake_post_json)
    jobs = public_ats._fetch_public_board_uncached(
        "workday",
        {"slug": "https://example.wd5.myworkdayjobs.com/en-US/External", "company": "Example", "country": "Sweden"},
    )

    assert len(jobs) == total
    assert requests[-1] == 420
    assert len(requests) == 22


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.mark.parametrize("module_name", ["lever", "teamtailor"])
def test_lever_and_teamtailor_retrieve_more_than_1000_jobs(monkeypatch, module_name):
    total = 1050
    if module_name == "lever":
        requests = []

        def fake_get(url, params=None, **kwargs):
            offset = int(params["skip"])
            limit = int(params["limit"])
            requests.append(offset)
            count = min(limit, total - offset)
            return FakeResponse([
                {
                    "id": f"lv-{offset + index}",
                    "text": f"Software Engineer {offset + index}",
                    "categories": {"location": "Stockholm, Sweden"},
                    "hostedUrl": f"https://jobs.lever.co/example/{offset + index}",
                }
                for index in range(count)
            ])

        monkeypatch.setattr(lever, "get_with_retries", fake_get)
        jobs = lever.fetch_site_jobs("example", company_name="Example", default_country="Sweden")
        assert len(jobs) == total
        assert requests[-1] == 1000
    else:
        requests = []

        def fake_get(url, params=None, **kwargs):
            page = int(params["page[number]"])
            limit = int(params["page[size]"])
            requests.append((page, limit))
            offset = (page - 1) * limit
            count = min(limit, total - offset)
            return FakeResponse({
                "data": [
                    {
                        "id": f"tt-{offset + index}",
                        "attributes": {"title": f"Software Engineer {offset + index}", "location": "Stockholm, Sweden", "body": "Build software."},
                        "links": {"careersite-job-url": f"https://example.teamtailor.com/jobs/{offset + index}"},
                    }
                    for index in range(count)
                ],
                "included": [],
                "meta": {"record-count": total, "page-count": (total + limit - 1) // limit},
            })

        monkeypatch.setattr(teamtailor, "get_with_retries", fake_get)
        jobs = teamtailor.fetch_company_jobs(api_key="local-test-key", company_name="Example", default_country="Sweden")
        assert len(jobs) == total
        assert requests[0] == (1, 30)
        assert requests[-1] == (35, 30)


def test_teamtailor_follows_next_link_and_never_requests_over_30(monkeypatch):
    requests = []
    pages = {
        1: [{"id": f"tt-{i}", "attributes": {"title": f"Software Engineer {i}", "location": "Stockholm"}} for i in range(30)],
        2: [{"id": "tt-30", "attributes": {"title": "Software Engineer 30", "location": "Stockholm"}}],
    }

    def fake_get(url, params=None, **kwargs):
        from urllib.parse import parse_qs, urlparse
        page = int(params["page[number]"]) if params else int(parse_qs(urlparse(url).query)["page[number]"][0])
        size = int(params["page[size]"]) if params else int(parse_qs(urlparse(url).query)["page[size]"][0])
        requests.append((page, size, kwargs["headers"]["authorization"]))
        payload = {"data": pages[page], "included": []}
        if page == 1:
            payload["links"] = {"next": "https://api.teamtailor.com/v1/jobs?page%5Bnumber%5D=2&page%5Bsize%5D=30"}
        return FakeResponse(payload)

    monkeypatch.setattr(teamtailor, "get_with_retries", fake_get)
    jobs = teamtailor.fetch_company_jobs(api_key="local-test-key", company_name="Example")
    assert len(jobs) == 31
    assert [item[:2] for item in requests] == [(1, 30), (2, 30)]
    assert all(item[2] == "Token token=local-test-key" for item in requests)


def test_teamtailor_rejects_next_link_to_untrusted_host(monkeypatch):
    def fake_get(url, params=None, **kwargs):
        return FakeResponse({
            "data": [{"id": "one", "attributes": {"title": "Software Engineer"}}],
            "links": {"next": "https://attacker.example/collect"},
        })

    monkeypatch.setattr(teamtailor, "get_with_retries", fake_get)
    with pytest.raises(JobSourceError, match="unexpected pagination URL"):
        teamtailor.fetch_company_jobs(api_key="local-test-key", company_name="Example")


def test_public_board_force_refresh_bypasses_recent_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(public_ats, "CACHE_DIR", tmp_path)
    board = {"slug": "example", "company": "Example", "country": "Sweden"}
    calls = []
    first_job = make_job(source_id="example:one")
    refreshed_job = make_job(source_id="example:two", id="ashby:legora:two")

    def fetch(*args, **kwargs):
        calls.append(True)
        return [first_job] if len(calls) == 1 else [refreshed_job]

    monkeypatch.setattr(public_ats, "_fetch_public_board_uncached", fetch)
    public_ats.fetch_public_board("ashby", board, force_refresh=True)
    cached = public_ats.fetch_public_board("ashby", board)
    assert len(calls) == 1
    assert cached[0].source_id == "example:one"

    fresh = public_ats.fetch_public_board("ashby", board, force_refresh=True)
    assert len(calls) == 2
    assert fresh[0].source_id == "example:two"


def test_public_board_uses_stale_snapshot_with_explicit_warning_on_refresh_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(public_ats, "CACHE_DIR", tmp_path)
    board = {"slug": "example", "company": "Example", "country": "Sweden"}
    initial_job = make_job(source="ashby", source_id="example:1", portal_id="ashby:example", company="Example")
    monkeypatch.setattr(public_ats, "_fetch_public_board_uncached", lambda *args, **kwargs: [initial_job])

    first = public_ats.fetch_public_board("ashby", board, force_refresh=True)
    assert len(first) == 1
    assert first[0].source_fetched_at

    def fail_refresh(*args, **kwargs):
        raise JobSourceError("upstream temporarily unavailable")

    monkeypatch.setattr(public_ats, "_fetch_public_board_uncached", fail_refresh)
    with pytest.raises(JobSourceStaleCacheError) as raised:
        public_ats.fetch_public_board("ashby", board, force_refresh=True)

    assert len(raised.value.cached_jobs) == 1
    assert "last successful" in str(raised.value).lower()
