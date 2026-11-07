import json
from pathlib import Path

from app.services.job_search import validate_source_config
from app.services.salary_normalizer import extract_salary
from app.services.platform_catalog import list_platforms
from app.services.resume_builder import _ats_score
from app.models.candidate import CandidateProfile


def test_platform_catalog_has_more_than_fifty_unique_platforms():
    items = list_platforms()
    assert len(items) >= 50
    assert len({item["id"] for item in items}) == len(items)
    assert all(item["integration"] in {"live", "configurable", "external"} for item in items)


def test_public_ats_boards_validate_without_api_keys():
    normalized = validate_source_config({
        "ashby": [{"enabled": True, "slug": "acme", "company": "Acme AB", "country": "Sweden"}],
        "workable": [{"enabled": False, "slug": "example"}],
    })
    assert normalized["ashby"][0]["slug"] == "acme"
    assert normalized["workable"][0]["enabled"] is False


def test_portal_registry_metadata_is_preserved_and_urls_must_be_https():
    normalized = validate_source_config({
        "greenhouse": [{
            "enabled": False,
            "board_token": "example-nordic",
            "company": "Example Nordic AB",
            "country": "Sweden",
            "career_url": "https://careers.example.com",
            "jobs_url": "https://boards.greenhouse.io/example-nordic",
            "notes": "Example only; replace with the company's actual public portal.",
        }]
    })
    entry = normalized["greenhouse"][0]
    assert entry["career_url"] == "https://careers.example.com"
    assert entry["jobs_url"] == "https://boards.greenhouse.io/example-nordic"
    assert entry["notes"].startswith("Example only")


def test_portal_registry_rejects_non_https_or_credential_bearing_urls():
    import pytest
    from app.services.job_sources.base import JobSourceError

    for invalid_url in (
        "http://careers.example.com",
        "javascript:alert(1)",
        "https://user:password@careers.example.com",
        "not-a-url",
    ):
        with pytest.raises(JobSourceError):
            validate_source_config({
                "lever": [{
                    "enabled": False,
                    "site": "example-nordic",
                    "company": "Example Nordic AB",
                    "career_url": invalid_url,
                }]
            })


def test_salary_parser_recognises_sek_range():
    assert extract_salary("Salary: SEK 40 000 - 55 000 per month") == {
        "salary_min": 40000, "salary_max": 55000, "salary_currency": "SEK"
    }


def test_salary_parser_does_not_invent_unknown_salary():
    assert extract_salary("Competitive salary depending on experience")["salary_min"] is None


def test_ats_score_returns_transparent_components():
    profile = CandidateProfile.model_validate({
        "personal": {"name":"A Candidate","email":"candidate@example.com"},
        "summary":"Python engineer with Kubernetes experience",
        "skills":["Python","Kubernetes"],
        "experience":[{"job_title":"Engineer","company":"Acme","description":["Built Python services on Kubernetes"]}],
        "education":[{"degree":"BSc","institution":"University"}]
    })
    result = _ats_score(profile, "Python Kubernetes engineer with production services", {
        "summary":"Python engineer with Kubernetes experience",
        "skills":["Python","Kubernetes"],
        "experience":[{"description":["Built Python services on Kubernetes"]}]
    })
    assert 0 <= result["score"] <= 100
    assert result["keyword_match_score"] > 0
    assert result["section_completeness_score"] >= 80
    assert result["threshold"] == 70
    assert result["disclaimer"]


def test_workday_board_requires_a_full_public_board_url():
    normalized = validate_source_config({
        "workday": [{"enabled": True, "slug": "https://example.wd5.myworkdayjobs.com/en-US/External"}]
    })
    assert normalized["workday"][0]["slug"].endswith("/External")


def test_platform_catalog_is_preserved_as_application_data_template(tmp_path):
    from app.services.data_management import reset_workspace_data
    (tmp_path / "platform_catalog.json").write_text("[]", encoding="utf-8")
    (tmp_path / "saved_searches.json").write_text("[]", encoding="utf-8")
    removed = reset_workspace_data(tmp_path)
    assert removed == 1
    assert (tmp_path / "platform_catalog.json").exists()
    assert not (tmp_path / "saved_searches.json").exists()


def test_workday_config_rejects_non_public_host():
    import pytest
    from app.services.job_sources.base import JobSourceError
    with pytest.raises(JobSourceError):
        validate_source_config({"workday":[{"enabled":True,"slug":"https://127.0.0.1:8000/internal"}]})


def test_salary_parser_supports_k_suffix():
    assert extract_salary("$100k - $150k") == {
        "salary_min": 100000, "salary_max": 150000, "salary_currency": "USD"
    }
