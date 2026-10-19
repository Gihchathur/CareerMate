"""Tests for local ATS board configuration and browser-answer fallbacks."""
import asyncio
import json

import pytest

from app.models.application import ApplicationRecord
from app.models.candidate import CandidateProfile, Experience
from app.services import browser_assistance, job_search
from app.services.job_sources.base import JobSourceError


class _Page:
    url = "https://careers.example.org/application"
    def is_closed(self):
        return False


class _Context:
    def __init__(self, page):
        self.pages = [page]


def test_browser_suggestions_use_reviewable_local_templates_if_model_returns_empty(monkeypatch, tmp_path):
    async def run():
        page = _Page()
        session = browser_assistance.ActiveBrowserSession(
            playwright=None, browser=None, context=_Context(page), page=page,
            application_id="application:fallback",
        )
        session.fields = {
            "cm-field-1": browser_assistance.BrowserField(
                field_id="cm-field-1", label="Why do you want to join this engineering team?",
                kind="textarea", required=True,
            ),
            "cm-field-2": browser_assistance.BrowserField(
                field_id="cm-field-2", label="What is the most impressive thing you have done in your career?",
                kind="textarea", required=True,
            ),
            "cm-field-3": browser_assistance.BrowserField(
                field_id="cm-field-3", label="What are your compensation expectations?",
                kind="text", required=True,
            ),
        }
        monkeypatch.setattr(browser_assistance, "_active_session", session)
        calls = []
        def fake_generate_text(prompt, **kwargs):
            calls.append(prompt)
            return json.dumps({"suggestions": []})
        monkeypatch.setattr(browser_assistance, "generate_text", fake_generate_text)
        monkeypatch.setattr(browser_assistance, "PROJECT_ROOT", tmp_path)
        (tmp_path / "data" / "cv").mkdir(parents=True)
        (tmp_path / "data" / "cv" / "extracted_text.txt").write_text("Platform engineer experienced with Kubernetes.", encoding="utf-8")
        application = ApplicationRecord(
            id="application:fallback", job_id="job:fallback", title="Platform Engineer",
            company="Example AB", job_description="Operate Kubernetes platforms and improve observability.",
        )
        profile = CandidateProfile(
            summary="Software engineer with platform engineering experience",
            skills=["Kubernetes", "Prometheus", "OpenTelemetry"],
            experience=[Experience(job_title="Engineer", company="Example", description=["Worked on Kubernetes services and observability dashboards"])],
        )
        result = await browser_assistance.suggest_browser_answers(
            application.id, list(session.fields), application, profile, page.url,
        )
        assert len(calls) == 2
        assert {item["field_id"] for item in result["suggestions"]} == {"cm-field-1", "cm-field-2"}
        assert all(item["source"].startswith("Local fallback") for item in result["suggestions"])
        assert all(item["value"] for item in result["suggestions"])
        assert "compensation" not in " ".join(item["field_id"] for item in result["suggestions"]).casefold()
        assert "personal motivation" in result["message"] or "local template" in result["message"].casefold()
    asyncio.run(run())


def test_source_config_save_and_load_round_trip(monkeypatch, tmp_path):
    config_path = tmp_path / "data" / "sources.json"
    monkeypatch.setattr(job_search, "SOURCE_CONFIG_PATH", config_path)
    supplied = {
        "greenhouse": [{"enabled": True, "board_token": "sample-board", "company": "Example AB", "country": "Sweden"}],
        "lever": [{"enabled": True, "site": "sample-site", "company": "Example Oy", "country": "Finland", "region": "eu"}],
        "teamtailor": [],
    }
    saved = job_search.save_source_config(supplied)
    assert saved["greenhouse"][0]["board_token"] == "sample-board"
    assert job_search.load_source_config() == saved


def test_source_config_rejects_teamtailor_secret_instead_of_env_name():
    with pytest.raises(JobSourceError, match="environment variable name"):
        job_search.validate_source_config({
            "greenhouse": [], "lever": [],
            "teamtailor": [{"enabled": True, "company": "Example", "api_key_env": "sk-secret-value", "region": "eu"}],
        })
