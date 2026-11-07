from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from app.services import portal_health


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://boards-api.greenhouse.io/test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)

    def json(self):
        return self._payload


def test_portal_health_marks_disabled_board_paused_and_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(portal_health, "HEALTH_PATH", tmp_path / "portal-health.json")
    monkeypatch.setattr(portal_health, "load_source_config", lambda: {
        "greenhouse": [{"enabled": False, "board_token": "example", "company": "Example AB", "country": "Sweden"}],
    })
    monkeypatch.setattr(portal_health, "SUPPORTED_ATS", ("greenhouse",))

    result = portal_health.check_portal_health()

    assert result["summary"]["total"] == 1
    assert result["summary"]["paused"] == 1
    assert result["items"][0]["status"] == "paused"
    saved = json.loads((tmp_path / "portal-health.json").read_text(encoding="utf-8"))
    assert saved["items"]["greenhouse:example"]["status"] == "paused"


def test_greenhouse_portal_health_counts_available_jobs(monkeypatch, tmp_path):
    monkeypatch.setattr(portal_health, "HEALTH_PATH", tmp_path / "portal-health.json")
    monkeypatch.setattr(portal_health, "load_source_config", lambda: {
        "greenhouse": [{"enabled": True, "board_token": "example", "company": "Example AB", "country": "Sweden"}],
    })
    monkeypatch.setattr(portal_health, "SUPPORTED_ATS", ("greenhouse",))
    monkeypatch.setattr(portal_health.httpx, "get", lambda *args, **kwargs: FakeResponse({"jobs": [{"id": 1}, {"id": 2}]}))

    result = portal_health.check_portal_health()

    assert result["summary"]["live"] == 1
    assert result["items"][0]["job_count"] == 2
    assert result["items"][0]["domain"] == "job-boards.greenhouse.io/example"


def test_teamtailor_without_key_is_needs_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(portal_health, "HEALTH_PATH", tmp_path / "portal-health.json")
    monkeypatch.setattr(portal_health, "load_source_config", lambda: {
        "teamtailor": [{"enabled": True, "company": "Example AB", "api_key_env": "CAREERMATE_TEST_MISSING_KEY", "region": "eu"}],
    })
    monkeypatch.setattr(portal_health, "SUPPORTED_ATS", ("teamtailor",))
    monkeypatch.delenv("CAREERMATE_TEST_MISSING_KEY", raising=False)
    monkeypatch.setattr(portal_health.httpx, "get", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("HTTP must not be called without credentials")))

    result = portal_health.check_portal_health()

    assert result["summary"]["needs_setup"] == 1
    assert result["items"][0]["status"] == "needs_setup"
    assert "CAREERMATE_TEST_MISSING_KEY" in result["items"][0]["message"]


def test_portal_health_reports_http_errors_without_leaking_request_details(monkeypatch, tmp_path):
    monkeypatch.setattr(portal_health, "HEALTH_PATH", tmp_path / "portal-health.json")
    monkeypatch.setattr(portal_health, "load_source_config", lambda: {
        "greenhouse": [{"enabled": True, "board_token": "missing-board", "company": "Missing AB", "country": "Sweden"}],
    })
    monkeypatch.setattr(portal_health, "SUPPORTED_ATS", ("greenhouse",))
    monkeypatch.setattr(portal_health.httpx, "get", lambda *args, **kwargs: FakeResponse({}, status_code=404))

    result = portal_health.check_portal_health()

    item = result["items"][0]
    assert item["status"] == "broken"
    assert item["message"] == "The portal returned HTTP 404."
    assert "missing-board" not in item["message"]


def test_get_portal_health_merges_cached_status_but_honours_pause(monkeypatch, tmp_path):
    health_path = tmp_path / "portal-health.json"
    health_path.write_text(json.dumps({
        "checked_at": "2026-11-07T10:00:00+00:00",
        "items": {
            "greenhouse:example": {
                "status": "live", "job_count": 12, "checked_at": "2026-11-07T10:00:00+00:00",
                "duration_ms": 120, "message": "Responding · 12 job(s) available."
            }
        }
    }), encoding="utf-8")
    monkeypatch.setattr(portal_health, "HEALTH_PATH", health_path)
    monkeypatch.setattr(portal_health, "load_source_config", lambda: {
        "greenhouse": [{"enabled": False, "board_token": "example", "company": "Example AB", "country": "Sweden"}],
    })
    monkeypatch.setattr(portal_health, "SUPPORTED_ATS", ("greenhouse",))

    result = portal_health.get_portal_health()

    assert result["items"][0]["status"] == "paused"
    assert result["items"][0]["job_count"] is None
