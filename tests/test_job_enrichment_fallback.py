from app.services import job_detail_enricher


class FakeResponse:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self, _chunk_size):
        yield b"<html><body><div id='app'>Please enable JavaScript.</div></body></html>"


class FakeClient:
    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stream(self, *_args, **_kwargs):
        return FakeResponse()


def test_static_javascript_shell_uses_bounded_render_fallback(monkeypatch):
    full_text = "Platform Engineer responsibilities and qualifications. " * 30
    seen = []
    monkeypatch.setattr(job_detail_enricher.httpx, "Client", FakeClient)
    monkeypatch.setattr(job_detail_enricher, "_check_public_https_url", lambda url: url)
    monkeypatch.setattr(
        job_detail_enricher,
        "_fetch_rendered_job_description",
        lambda url: seen.append(url) or full_text,
    )

    result = job_detail_enricher.fetch_public_job_description("https://example.com/jobs/platform")

    assert result == full_text
    assert seen == ["https://example.com/jobs/platform"]


def test_empty_requirement_assessment_does_not_invent_a_score(tmp_path, monkeypatch):
    import json
    from app.services import job_matcher

    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("openai_compatible", "test-model"))
    monkeypatch.setattr(
        job_matcher,
        "generate_text",
        lambda *_args, **_kwargs: json.dumps({"requirements": [], "summary": "The advert text contained no assessable requirements."}),
    )
    job = {
        "id": "test:empty-criteria", "title": "Platform Engineer", "company": "Example",
        "description": "Job description text. " * 40, "description_source": "original_listing",
        "description_fetch_message": "Manually pasted advert text saved locally; source is not independently verified.",
    }
    profile = {"summary": "Platform engineer", "skills": ["Kubernetes"], "experience": [], "education": [], "certifications": [], "languages": ["English"]}

    result = job_matcher.score_job(job, profile)

    assert result["match_score"] is None
    assert result["requirements"] == []
    assert result["job_description_source"] == "original_listing"
    assert "manually pasted" in result["score_note"].casefold()
    assert "not a probability" in result["score_note"]


def test_unweighted_requirements_explain_why_score_is_hidden(tmp_path, monkeypatch):
    import json
    from app.services import job_matcher

    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("openai_compatible", "test-model"))
    monkeypatch.setattr(
        job_matcher,
        "generate_text",
        lambda *_args, **_kwargs: json.dumps({
            "summary": "The source uses vague wording.",
            "requirements": [{
                "requirement": "Broad familiarity with platform tooling",
                "category": "skill", "importance": "unclear", "criticality": "important",
                "status": "supported", "evidence": "Kubernetes", "explanation": "The profile lists Kubernetes.",
            }],
        }),
    )
    job = {"id": "test:unweighted", "title": "Engineer", "description": "Platform tooling role. " * 50, "description_source": "original_listing"}
    profile = {"summary": "Platform engineer", "skills": ["Kubernetes"], "experience": [], "education": [], "certifications": [], "languages": ["English"]}

    result = job_matcher.score_job(job, profile)

    assert result["match_score"] is None
    assert "none of the extracted requirements was classified as required or preferred" in result["match_explanation"]
