import json
from pathlib import Path

from app.services import job_matcher


def _valid_analysis() -> str:
    return json.dumps({
        "summary": "The advert asks for Kubernetes experience.",
        "requirements": [{
            "requirement": "Experience with Kubernetes",
            "category": "skill",
            "importance": "required",
            "criticality": "important",
            "status": "supported",
            "evidence": "Kubernetes",
            "explanation": "The profile explicitly lists Kubernetes.",
        }],
    })


def _job() -> dict:
    return {
        "id": "test:json-truncated",
        "title": "Platform Engineer",
        "company": "Example AB",
        "description": "Build and operate Kubernetes platforms. " * 50,
        "description_source": "original_listing",
    }


def _profile() -> dict:
    return {
        "summary": "Platform engineer experienced with Kubernetes.",
        "skills": ["Kubernetes"],
        "experience": [],
        "education": [],
        "certifications": [],
        "languages": ["English"],
    }


def test_truncated_json_retries_once_and_returns_score(tmp_path, monkeypatch):
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("openai_compatible", "test-model"))
    calls = []

    def fake_generate(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return '{"requirements":[{"requirement":"Experience with Kubernetes",' if len(calls) == 1 else _valid_analysis()

    monkeypatch.setattr(job_matcher, "generate_text", fake_generate)

    result = job_matcher.score_job(_job(), _profile())

    assert len(calls) == 2
    assert calls[0][1]["max_tokens"] == 3600
    assert "Regenerate the ENTIRE JSON object" in calls[1][0]
    assert result["match_score"] == 100
    assert len(result["requirements"]) == 1


def test_two_invalid_json_responses_fail_cleanly_without_leaking_raw_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("openai_compatible", "test-model"))
    calls = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        return '{"requirements":[{"requirement":"truncated secret-ish content'

    monkeypatch.setattr(job_matcher, "generate_text", fake_generate)

    result = job_matcher.score_job(_job(), _profile())

    assert len(calls) == 2
    assert result["match_score"] is None
    assert "incomplete or invalid structured output twice" in result["match_explanation"]
    assert "input_value" not in result["match_explanation"]
    assert "truncated secret-ish content" not in result["match_explanation"]
