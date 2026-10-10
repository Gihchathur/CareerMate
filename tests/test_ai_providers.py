import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models.candidate import CandidateProfile
from app.services import ai_provider
from app.services.ai_provider import AIProviderError, generate_text, get_ai_settings, save_ai_settings


def test_settings_require_consent_before_saving_cloud_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    with pytest.raises(AIProviderError, match="Confirm that profile/CV content"):
        save_ai_settings("openai", "gpt-6-luna", confirm_cloud_data_sharing=False)
    assert not (tmp_path / "settings.json").exists()


def test_saved_settings_never_store_api_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-not-to-save")
    save_ai_settings("openai", "gpt-6-luna", confirm_cloud_data_sharing=True)
    saved = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "test-secret-not-to-save" not in saved
    data = json.loads(saved)
    assert data["provider"] == "openai"
    result = get_ai_settings()
    assert result["providers"]["openai"]["api_key_configured"] is True
    assert "api_key" not in result["providers"]["openai"]


def test_remote_compatible_endpoint_requires_https(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    with pytest.raises(AIProviderError, match="Use HTTPS"):
        save_ai_settings(
            "openai_compatible", "provider-model", "http://api.example.com/v1",
            confirm_cloud_data_sharing=True,
        )
    # Plain HTTP remains available to loopback services such as local test APIs.
    monkeypatch.setenv("CAREERMATE_OPENAI_COMPATIBLE_API_KEY", "test-key")
    result = save_ai_settings(
        "openai_compatible", "local-model", "http://127.0.0.1:1234/v1",
        confirm_cloud_data_sharing=True,
    )
    assert result["providers"]["openai_compatible"]["base_url"] == "http://127.0.0.1:1234/v1"


def test_openai_strict_schema_marks_all_object_properties_required():
    schema = CandidateProfile.model_json_schema()
    normalized = ai_provider._strict_json_schema(schema)
    assert normalized["additionalProperties"] is False
    assert set(normalized["required"]) == set(normalized["properties"])
    candidate_personal = normalized["$defs"]["CandidatePersonal"]
    assert candidate_personal["additionalProperties"] is False
    assert set(candidate_personal["required"]) == set(candidate_personal["properties"])


def test_openai_provider_uses_responses_api_and_structured_output(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.responses = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(output_text='{"summary":"test"}')

    fake_module = ModuleType("openai")
    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    monkeypatch.setattr(ai_provider, "_runtime_config", lambda *a, **k: {
        "provider": "openai", "model": "gpt-6-luna", "base_url": "", "api_key": "test-key",
    })

    result = generate_text("return JSON", json_schema={"type": "object", "properties": {"summary": {"type": "string"}}})
    assert result == '{"summary":"test"}'
    assert captured["request"]["text"]["format"]["type"] == "json_schema"
    assert captured["request"]["text"]["format"]["strict"] is True
    assert captured["client"]["api_key"] == "test-key"


def test_compatible_provider_uses_json_mode(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            chat_completions = SimpleNamespace(create=self.create)
            self.chat = SimpleNamespace(completions=chat_completions)

        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    fake_module = ModuleType("openai")
    fake_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    monkeypatch.setattr(ai_provider, "_runtime_config", lambda *a, **k: {
        "provider": "openai_compatible", "model": "provider-model", "base_url": "https://example.com/v1", "api_key": "test-key",
    })

    assert generate_text("return JSON", json_schema={"type": "object"}) == '{"ok":true}'
    assert captured["request"]["response_format"] == {"type": "json_object"}
    assert captured["client"]["base_url"] == "https://example.com/v1"


def test_settings_api_requires_cloud_data_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    response = TestClient(main.app).put("/api/ai/settings", json={
        "provider": "openai", "model": "gpt-6-luna", "base_url": "", "confirm_cloud_data_sharing": False,
    })
    assert response.status_code == 400
    assert "Confirm" in response.json()["detail"]


def test_ai_test_endpoint_uses_only_a_non_personal_ping(monkeypatch):
    captured = {}
    def fake_test(provider, model, base_url=""):
        captured.update(provider=provider, model=model, base_url=base_url)
        return {"success": True, "provider": provider, "model": model, "message": "CareerMate connection successful."}

    monkeypatch.setattr(main, "test_provider_connection", fake_test)
    response = TestClient(main.app).post("/api/ai/test", json={
        "provider": "openai", "model": "gpt-6-luna", "base_url": "",
    })
    assert response.status_code == 200
    assert captured["provider"] == "openai"
    assert response.json()["success"] is True


def test_cv_analysis_uses_the_shared_selected_provider(tmp_path, monkeypatch):
    from app.services import cv_analyzer

    cv_dir = tmp_path / "cv"
    cv_dir.mkdir()
    text_path = cv_dir / "extracted_text.txt"
    text_path.write_text("Example Candidate\nPython and platform engineering experience.", encoding="utf-8")
    profile_path = cv_dir / "profile.json"
    monkeypatch.setattr(cv_analyzer, "EXTRACTED_TEXT_PATH", text_path)
    monkeypatch.setattr(cv_analyzer, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(cv_analyzer, "get_active_provider_identity", lambda: ("openai", "gpt-6-luna"))
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["schema"] = kwargs["json_schema"]
        return CandidateProfile.model_validate({"personal": {"name": "Example Candidate"}, "skills": ["Python"]}).model_dump_json()

    monkeypatch.setattr(cv_analyzer, "generate_text", fake_generate)
    profile = cv_analyzer.analyze_cv()

    assert profile.personal.name == "Example Candidate"
    assert profile.skills == ["Python"]
    assert profile_path.exists()
    assert "Example Candidate" in captured["prompt"]
    assert captured["schema"]["type"] == "object"


def test_cover_letter_generation_uses_shared_provider_layer(monkeypatch):
    from app.models.application import ApplicationRecord
    from app.services import application_drafts

    captured = {}
    monkeypatch.setattr(application_drafts, "get_active_provider_identity", lambda: ("openai", "gpt-6-luna"))

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return "Dear hiring team, this is a draft."

    monkeypatch.setattr(application_drafts, "generate_text", fake_generate)
    profile = CandidateProfile.model_validate({"personal": {"name": "Example Candidate"}, "summary": "Platform engineering"})
    application = ApplicationRecord(id="app-1", job_id="job-1", title="Engineer", company="Example", job_description="Platform role")

    result = application_drafts.generate_cover_letter(application, profile)

    assert result.startswith("Dear hiring team")
    assert captured["kwargs"]["max_tokens"] == 1200
    assert "Platform engineering" in captured["prompt"]


def test_cloud_matching_uses_four_way_bounded_concurrency(tmp_path, monkeypatch):
    import threading
    import time

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(CandidateProfile.model_validate({"summary": "Platform engineering"}).model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(main, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(main, "load_saved_jobs", lambda: [
        {"id": f"job-{i}", "title": f"Role {i}", "company": "Example"} for i in range(4)
    ])
    monkeypatch.setattr(main, "get_active_provider_identity", lambda: ("openai", "gpt-6-luna"))
    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_score(job, _profile):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return {
            "match_score": 50, "match_confidence": "medium", "match_method": "test",
            "matched_skills": [], "matched_requirements": [], "partially_matched_requirements": [],
            "missing_requirements": [], "requirements": [], "match_explanation": "test", "score_note": "test",
        }

    monkeypatch.setattr(main, "score_job", fake_score)
    response = TestClient(main.app).get("/api/jobs/matches?limit=4")

    assert response.status_code == 200
    assert response.json()["concurrency"] == 4
    assert response.json()["analyzed"] == 4
    assert peak > 1


def test_match_cache_key_changes_when_provider_or_model_changes(tmp_path, monkeypatch):
    from app.services import job_matcher

    monkeypatch.setattr(job_matcher, "CACHE_PATH", tmp_path / "cache.json")
    job = {"id": "job-1", "title": "Engineer", "description": "Platform role"}
    profile = {"skills": ["Python"]}
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("ollama", "gemma4:e4b"))
    local_key = job_matcher._cache_key(job, profile)
    monkeypatch.setattr(job_matcher, "get_active_provider_identity", lambda: ("openai", "gpt-6-luna"))
    cloud_key = job_matcher._cache_key(job, profile)
    assert local_key != cloud_key



def test_active_cloud_provider_requires_explicit_data_sharing_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "missing-settings.json")
    monkeypatch.setenv("CAREERMATE_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(AIProviderError, match="explicitly confirm"):
        ai_provider._runtime_config()


def test_compatible_base_url_rejects_query_or_fragment_that_could_leak_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    with pytest.raises(AIProviderError, match="without embedded credentials"):
        save_ai_settings(
            "openai_compatible", "provider-model", "https://api.example.com/v1?token=secret",
            confirm_cloud_data_sharing=True,
        )



def test_hosted_provider_is_not_reported_ready_before_data_sharing_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "missing-settings.json")
    monkeypatch.setenv("CAREERMATE_AI_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = get_ai_settings()
    assert result["providers"]["openai"]["api_key_configured"] is True
    assert result["providers"]["openai"]["configured"] is False
    assert result["cloud_data_sharing_acknowledged"] is False



def test_saving_hosted_provider_requires_key_to_be_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AIProviderError, match="OpenAI API key is missing"):
        save_ai_settings("openai", "gpt-6-luna", confirm_cloud_data_sharing=True)
    assert not (tmp_path / "settings.json").exists()
