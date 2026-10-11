import json

import pytest

from app.models.application import ApplicationRecord
from app.services import job_detail_enricher, job_matcher, job_storage, application_drafts
from app.services.job_detail_enricher import JobDetailFetchError, _check_public_https_url, _html_to_text, enrich_job_record


def test_html_parser_keeps_job_content_and_skips_navigation_and_footer():
    html = """
    <html><body><nav>Menu Account Register</nav><main>
      <h1>Senior Engineer</h1><h2>What you will do</h2>
      <ul><li>Own features from idea to launch</li><li>Improve production .NET systems</li></ul>
    </main><footer>Privacy Main partners Subscribe</footer></body></html>
    """
    text = _html_to_text(html)
    assert "Senior Engineer" in text
    assert "Own features from idea to launch" in text
    assert "Menu Account Register" not in text
    assert "Privacy Main partners" not in text


def test_html_parser_prefers_structured_jobposting_description_when_available():
    description = "Lead features from discovery to delivery. " * 30
    payload = json.dumps({"@context": "https://schema.org", "@type": "JobPosting", "title": "Engineer", "description": f"<p>{description}</p>", "employmentType": "FULL_TIME"})
    html = f"<html><body><nav>{'Menu ' * 80}</nav><main><h1>Engineer</h1><p>Short teaser only.</p></main><script type='application/ld+json'>{payload}</script></body></html>"
    text = _html_to_text(html)
    assert "Description:" in text
    assert text.count("Lead features") >= 1
    assert "Short teaser only" not in text


def test_public_listing_fetch_rejects_http_and_local_addresses():
    with pytest.raises(JobDetailFetchError, match="HTTPS"):
        _check_public_https_url("http://example.com/jobs/1")
    with pytest.raises(JobDetailFetchError, match="Local or internal"):
        _check_public_https_url("https://localhost/jobs/1")
    with pytest.raises(JobDetailFetchError, match="Private or reserved"):
        _check_public_https_url("https://127.0.0.1/jobs/1")


def test_enrichment_updates_description_source_and_timestamp(monkeypatch):
    monkeypatch.setattr(job_detail_enricher, "fetch_public_job_description", lambda _url: "FULL DESCRIPTION " * 80)
    job = {
        "id": "source:1", "source": "jobtech_links", "source_id": "1",
        "title": "Engineer", "company": "Example", "location": "Stockholm",
        "description": "Short teaser.", "source_url": "https://example.com/jobs/1", "apply_url": "https://example.com/jobs/1",
    }
    enriched = enrich_job_record(job)
    assert enriched["description_source"] == "original_listing"
    assert enriched["description_fetch_status"] == "success"
    assert enriched["description_fetched_at"]
    assert len(enriched["description"]) > len(job["description"])
    assert job["description"] == "Short teaser."


def test_saved_search_snippet_does_not_overwrite_full_original_description(tmp_path, monkeypatch):
    monkeypatch.setattr(job_storage, "JOBS_PATH", tmp_path / "jobs.json")
    full_job = {
        "id": "source:1", "source": "jobtech_links", "source_id": "1",
        "title": "Engineer", "company": "Example", "location": "Stockholm",
        "description": "Full original description and requirements.",
        "description_source": "original_listing", "description_fetch_status": "success",
        "source_url": "https://example.com/jobs/1", "apply_url": "https://example.com/jobs/1",
    }
    snippet = {**full_job, "description": "Short search snippet.", "description_source": "search_result", "description_fetch_status": "not_attempted"}
    job_storage.save_jobs([full_job])
    job_storage.save_jobs([snippet])
    saved = job_storage.load_saved_jobs()[0]
    assert saved["description"] == full_job["description"]
    assert saved["description_source"] == "original_listing"


def test_match_analysis_surfaces_critical_gap_and_does_not_make_swedish_plus_critical(tmp_path, monkeypatch):
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    model_response = {
        "summary": "The candidate supports .NET but the experience threshold needs review.",
        "requirements": [
            {
                "requirement": "7+ years of professional software engineering experience",
                "category": "experience", "importance": "required", "status": "partially_supported",
                "evidence": "over 4 years of engineering experience", "explanation": "Profile indicates fewer years than the stated threshold.",
            },
            {
                "requirement": "Strong production experience with C# and .NET",
                "category": "skill", "importance": "required", "status": "supported",
                "evidence": "production systems using C# and .NET", "explanation": "Direct production experience is listed.",
            },
            {
                "requirement": "Swedish language skills are a plus",
                "category": "language", "importance": "preferred", "status": "not_evidenced",
                "evidence": "", "explanation": "No Swedish language level is listed in the profile.",
            },
        ],
    }
    monkeypatch.setattr(job_matcher, "generate_text", lambda *_args, **_kwargs: json.dumps(model_response))
    job = {"id": "devolens:1", "title": "Senior Fullstack Product Engineer", "company": "Devolens", "location": "Stockholm hybrid", "description": "A detailed role requiring 7+ years of experience in a mature .NET product." * 30, "description_source": "original_listing"}
    profile = {
        "personal": {"name": "Example", "email": "private@example.com"},
        "summary": "Software engineer with over 4 years of engineering experience and production systems using C# and .NET.",
        "skills": ["C#", ".NET"], "experience": [], "education": [], "certifications": [], "languages": ["English"],
    }
    result = job_matcher.score_job(job, profile)
    assert result["recommendation"] == "review_critical_gaps"
    assert any("7+ years" in item["requirement"] for item in result["critical_gaps"])
    swedish = next(item for item in result["requirements"] if "Swedish" in item["requirement"])
    assert swedish["criticality"] == "nice_to_have"
    assert result["job_description_source"] == "original_listing"


def test_short_cover_letter_gets_one_retry_before_failing(monkeypatch, tmp_path):
    monkeypatch.setattr(application_drafts, "CV_TEXT_PATH", tmp_path / "no-cv.txt")
    monkeypatch.setattr(application_drafts, "get_active_provider_identity", lambda: ("openai_compatible", "gemini-test"))
    responses = iter(["I am interested in this role.", "I am interested in this role."])
    calls = []

    def fake_generate(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return next(responses)

    monkeypatch.setattr(application_drafts, "generate_text", fake_generate)
    app = ApplicationRecord(id="application:test", job_id="job:test", title="Engineer", company="Example", job_description="Role details")
    with pytest.raises(application_drafts.DraftGenerationError, match="quality limits"):
        application_drafts.generate_cover_letter(app, __import__("app.models.candidate", fromlist=["CandidateProfile"]).CandidateProfile.model_validate({"summary": "Software engineering"}))
    assert len(calls) == 2
    assert "QUALITY GATE" in calls[1][0]
    assert calls[0][1]["max_tokens"] == 3000


def test_sanitized_cv_text_redacts_contact_channels(tmp_path, monkeypatch):
    cv = tmp_path / "cv.txt"
    cv.write_text("Software engineer\nEmail: candidate@example.com\nPhone: +46 70 123 4567\nSkills: Python and C#\nhttps://portfolio.example/profile", encoding="utf-8")
    monkeypatch.setattr(application_drafts, "CV_TEXT_PATH", cv)
    result = application_drafts._sanitized_cv_text()
    assert "candidate@example.com" not in result
    assert "+46 70 123 4567" not in result
    assert "https://portfolio.example/profile" not in result
    assert "Python and C#" in result


def test_job_enrichment_endpoint_saves_full_description(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import main

    job = {
        "id": "jobtech-links:enrich-1", "source": "jobtech_links", "source_id": "enrich-1",
        "title": "Senior Product Engineer", "company": "Devolens", "location": "Stockholm",
        "description": "Short snippet.", "source_url": "https://thehub.io/jobs/example",
        "apply_url": "https://thehub.io/jobs/example", "description_source": "search_result",
    }
    stored = {}
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [job])
    monkeypatch.setattr(main, "save_jobs", lambda incoming: stored.update(incoming[0]) or 1)
    full = {**job, "description": "Full employer description. " * 100, "description_source": "original_listing", "description_fetch_status": "success", "description_fetched_at": "2026-10-10T00:00:00+00:00"}
    monkeypatch.setattr(main, "_try_enrich_job", lambda _job, force=False: full)

    response = TestClient(main.app).post("/api/jobs/enrich", json={"job_id": job["id"]})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["job"]["description_source"] == "original_listing"
    assert stored["description"].startswith("Full employer description")


def test_match_endpoint_scores_the_enriched_description(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.models.candidate import CandidateProfile

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(CandidateProfile.model_validate({"summary": "Experienced software engineer"}).model_dump_json(), encoding="utf-8")
    job = {"id": "job-1", "title": "Engineer", "company": "Example", "description": "Short teaser", "source_url": "https://example.com/jobs/1", "description_source": "search_result"}
    full_job = {**job, "description": "Long requirements and responsibilities. " * 100, "description_source": "original_listing", "description_fetch_status": "success"}
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [job])
    monkeypatch.setattr(main, "_try_enrich_job", lambda _job, force=False: full_job)
    monkeypatch.setattr(main, "save_jobs", lambda _jobs: 1)
    seen = {}

    def fake_score(candidate_job, _profile):
        seen["description"] = candidate_job["description"]
        return {"match_score": 80, "match_confidence": "high", "match_method": "test", "matched_skills": [], "matched_requirements": [], "partially_matched_requirements": [], "missing_requirements": [], "requirements": [], "critical_gaps": [], "required_gaps_count": 0, "recommendation": "strong_potential_fit", "recommendation_label": "Strong potential fit", "recommendation_explanation": "test", "job_description_source": "original_listing", "match_explanation": "test", "score_note": "test"}

    monkeypatch.setattr(main, "score_job", fake_score)
    response = TestClient(main.app).get("/api/jobs/matches?limit=1&job_ids=job-1")
    assert response.status_code == 200
    assert "Long requirements" in seen["description"]
    assert response.json()["jobs"][0]["description_source"] == "original_listing"


def test_short_cover_letter_is_retried_and_complete_second_response_is_returned(monkeypatch, tmp_path):
    from app.models.candidate import CandidateProfile
    monkeypatch.setattr(application_drafts, "CV_TEXT_PATH", tmp_path / "no-cv.txt")
    monkeypatch.setattr(application_drafts, "get_active_provider_identity", lambda: ("openai_compatible", "gemini-test"))
    long_draft = (
        "Dear hiring team,\n\n"
        + ("I have relevant software engineering experience and would connect my verified skills to your team needs. " * 4)
        + "\n\n"
        + ("My recent work has included building and maintaining production services, and I take care to consider reliability and maintainability. " * 4)
        + "\n\n"
        + ("I would bring a practical approach to delivery, testing, troubleshooting, and collaborating with colleagues on customer needs. " * 4)
        + "\n\n"
        + ("I would welcome the opportunity to discuss how the experience supported by my CV could contribute to your team. " * 4)
        + "\n\nKind regards,\nExample Candidate"
    )
    responses = iter(["I am interested in this role.", long_draft])
    calls = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        return next(responses)

    monkeypatch.setattr(application_drafts, "generate_text", fake_generate)
    app = ApplicationRecord(id="application:test", job_id="job:test", title="Engineer", company="Example", job_description="Role details")
    result = application_drafts.generate_cover_letter(app, CandidateProfile.model_validate({"summary": "Software engineering"}))
    assert len(calls) == 2
    assert "QUALITY GATE" in calls[1]
    assert len(result.split()) >= 200


def test_enrichment_tries_source_and_application_urls_and_keeps_fullest_text(monkeypatch):
    short_page = "Role title and overview. " * 30
    full_page = "Full responsibilities, qualifications, seniority thresholds and working model. " * 90
    seen = []

    def fake_fetch(url):
        seen.append(url)
        if "listing.example" in url:
            return short_page
        return full_page

    monkeypatch.setattr(job_detail_enricher, "fetch_public_job_description", fake_fetch)
    job = {
        "id": "source:dual-link", "title": "Engineer", "company": "Example",
        "description": "short", "source_url": "https://listing.example/jobs/1",
        "apply_url": "https://apply.example/jobs/1",
    }
    result = enrich_job_record(job, force=True)
    assert seen == [job["source_url"], job["apply_url"]]
    assert result["description_source"] == "original_listing"
    assert "Full responsibilities" in result["description"]


def test_match_from_search_snippet_is_explicitly_provisional(tmp_path, monkeypatch):
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    model_response = {
        "summary": "The snippet only mentions the main stack.",
        "requirements": [
            {
                "requirement": "Strong production experience with C# and .NET",
                "category": "skill", "importance": "required", "criticality": "important",
                "status": "supported", "evidence": "production systems using C# and .NET",
                "explanation": "The profile directly names production C#/.NET work.",
            },
            {
                "requirement": "7+ years of software engineering experience",
                "category": "experience", "importance": "required", "criticality": "critical",
                "status": "partially_supported", "evidence": "over 4 years of engineering experience",
                "explanation": "The stated threshold is higher than the evidenced duration.",
            },
        ],
    }
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        assert "Aim for 10–18 distinct material requirements" in prompt
        return json.dumps(model_response)

    monkeypatch.setattr(job_matcher, "generate_text", fake_generate)
    job = {
        "id": "snippet:1", "title": "Senior Engineer", "company": "Example",
        "description": "Search teaser mentioning .NET and Stockholm.",
        "description_source": "search_result",
    }
    profile = {
        "summary": "Software engineer with over 4 years of engineering experience and production systems using C# and .NET.",
        "skills": ["C#", ".NET"], "experience": [], "education": [],
        "certifications": [], "languages": ["English"],
    }
    result = job_matcher.score_job(job, profile)
    assert result["recommendation"] == "incomplete_description"
    assert result["recommendation_label"] == "Full job advert needed"
    assert result["match_confidence"] == "low"
    assert result["description_complete"] is False
    assert "PRELIMINARY" in result["score_note"]
    assert any("7+ years" in item["requirement"] for item in result["critical_gaps"])
    assert captured["max_tokens"] == 2400
    assert captured["context_window"] == 8192


def test_hard_year_threshold_stays_critical_even_if_model_marks_preferred():
    item = job_matcher.RequirementAssessment.model_validate({
        "requirement": "7+ years of professional software engineering experience",
        "category": "experience", "importance": "preferred", "status": "not_evidenced",
        "evidence": "", "explanation": "Experience requirement",
    })
    assert job_matcher._normalize_criticality(item) == "critical"


def test_explicitly_optional_year_threshold_is_not_made_critical():
    item = job_matcher.RequirementAssessment.model_validate({
        "requirement": "7+ years of experience would be a plus, but is not required",
        "category": "experience", "importance": "preferred", "status": "not_evidenced",
        "evidence": "", "explanation": "Optional bonus",
    })
    assert job_matcher._normalize_criticality(item) == "nice_to_have"


def test_cover_letter_endpoint_refuses_to_save_generic_draft_from_short_snippet(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from app.models.candidate import CandidateProfile
    from app.services import application_storage

    app_path = tmp_path / "applications.json"
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(application_storage, "APPLICATIONS_PATH", app_path)
    short_job = {**{
        "id": "short:1", "source": "test", "source_id": "1", "title": "Engineer",
        "company": "Example", "location": "Stockholm", "description": "Only a short snippet.",
        "published_at": "", "source_url": "https://example.com/jobs/1", "apply_url": "https://example.com/jobs/1",
    }}
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [short_job])
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    profile_path.write_text(CandidateProfile.model_validate({"summary": "Software engineer"}).model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(main, "_refresh_application_description", lambda application, force=False: application)
    called = {"value": False}
    monkeypatch.setattr(main, "generate_cover_letter", lambda *_args: called.update(value=True) or "should not happen")

    client = TestClient(main.app)
    created = client.post("/api/applications", json={"job_id": short_job["id"]}).json()["application"]
    response = client.post(f"/api/applications/{created['id']}/draft-cover-letter")

    assert response.status_code == 409
    assert "short search snippet" in response.json()["detail"]
    assert called["value"] is False


def test_cover_letter_quality_rejects_overlong_drafts():
    from app.services.application_drafts import _cover_letter_quality

    overlong = "Dear hiring team\n\n" + (("This is a sentence that adds more length without adding new evidence. " * 100) + "\n\n") * 5 + "Kind regards\nCandidate"
    complete, words, paragraphs = _cover_letter_quality(overlong)
    assert words > 420
    assert paragraphs >= 4
    assert complete is False


def test_explicit_saved_stockholm_location_overrides_model_false_negative(tmp_path, monkeypatch):
    from app.services import job_matcher
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    model_response = {
        "summary": "The model incorrectly missed explicit profile facts.",
        "requirements": [{
            "requirement": "Ability to work from Stockholm regularly",
            "category": "other",
            "importance": "required",
            "criticality": "critical",
            "status": "not_evidenced",
            "evidence": "",
            "explanation": "The profile does not mention Stockholm.",
        }],
    }
    monkeypatch.setattr(job_matcher, "generate_text", lambda *_args, **_kwargs: json.dumps(model_response))
    profile = {
        "personal": {"location": "Stockholm, Sweden", "email": "private@example.com"},
        "summary": "Software Engineer with 4+ years of experience.",
        "skills": ["C#", ".NET"], "experience": [], "education": [],
        "certifications": [], "languages": ["English"],
    }
    job = {"id": "loc:1", "title": "Engineer", "location": "Stockholm", "description": "Ability to work from Stockholm regularly. " * 20, "description_source": "original_listing"}

    result = job_matcher.score_job(job, profile)

    location = next(item for item in result["requirements"] if "Stockholm" in item["requirement"])
    assert location["category"] == "location"
    assert location["status"] == "supported"
    assert location["evidence"] == "Stockholm, Sweden"
    assert location["criticality"] != "critical"
    assert "private@example.com" not in json.dumps(result)


def test_explicit_english_is_not_reported_missing_for_communication_requirement(tmp_path, monkeypatch):
    from app.services import job_matcher
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    model_response = {
        "summary": "The profile lists English but does not show proficiency level.",
        "requirements": [{
            "requirement": "Strong communication skills in English",
            "category": "other",
            "importance": "required",
            "criticality": "critical",
            "status": "not_evidenced",
            "evidence": "",
            "explanation": "The profile does not mention English.",
        }],
    }
    monkeypatch.setattr(job_matcher, "generate_text", lambda *_args, **_kwargs: json.dumps(model_response))
    profile = {
        "personal": {"location": "Stockholm, Sweden"},
        "summary": "Software Engineer.", "skills": [], "experience": [],
        "education": [], "certifications": [], "languages": ["English"],
    }
    job = {"id": "lang:1", "title": "Engineer", "description": "Strong communication skills in English. " * 20, "description_source": "original_listing"}

    result = job_matcher.score_job(job, profile)

    language = result["requirements"][0]
    assert language["category"] == "language"
    assert language["status"] == "partially_supported"
    assert language["evidence"] == "English"
    assert language["criticality"] == "important"


def test_dotnet_web_experience_is_partial_not_absent_for_mvc_razor(tmp_path, monkeypatch):
    from app.services import job_matcher
    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "match_cache.json")
    model_response = {
        "summary": "The profile has related .NET/web experience but not framework-specific evidence.",
        "requirements": [{
            "requirement": "Experience with ASP.NET MVC and Razor UI",
            "category": "skill", "importance": "required", "criticality": "critical",
            "status": "not_evidenced", "evidence": "", "explanation": "MVC/Razor is not named.",
        }],
    }
    monkeypatch.setattr(job_matcher, "generate_text", lambda *_args, **_kwargs: json.dumps(model_response))
    profile = {
        "personal": {"location": "Stockholm, Sweden"},
        "summary": "Software engineer who developed a web application with C# and .NET.",
        "skills": ["C#", ".NET"], "experience": [], "education": [],
        "certifications": [], "languages": ["English"],
    }
    job = {"id": "tech:1", "title": "Engineer", "description": "Experience with ASP.NET MVC and Razor UI. " * 20, "description_source": "original_listing"}

    result = job_matcher.score_job(job, profile)

    item = result["requirements"][0]
    assert item["status"] == "partially_supported"
    assert item["evidence"] in {".NET", "C#"}
    assert "does not explicitly name MVC/Razor" in item["explanation"]
    assert item["criticality"] == "important"


def test_candidate_facts_include_location_but_exclude_contact_data():
    from app.services.job_matcher import _candidate_facts
    facts = _candidate_facts({
        "personal": {
            "name": "Example", "email": "private@example.com", "phone": "+46700000000",
            "location": "Stockholm, Sweden", "linkedin": "https://linkedin.example/user",
        },
        "languages": ["English"], "skills": [], "experience": [], "education": [], "certifications": [],
    })
    assert facts["current_location"] == "Stockholm, Sweden"
    assert facts["languages"] == ["English"]
    serialized = json.dumps(facts)
    assert "private@example.com" not in serialized
    assert "+46700000000" not in serialized
    assert "linkedin.example" not in serialized
