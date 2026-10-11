from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import data_management
from app.services.browser_assistance import _browser_failure_message


def _write(path: Path, content: str = "[]") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_data_summary_reports_counts_without_reading_private_content(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _write(data_root / "cv" / "current.pdf", "personal-cv-bytes")
    _write(data_root / "cv" / "extracted_text.txt", "very private cv text")
    _write(data_root / "cv" / "profile.json", json.dumps({"name": "private"}))
    _write(data_root / "cv" / "profile.example.json", "{}")
    _write(data_root / "jobs" / "jobs.json", '[{"id":"1"},{"id":"2"}]')
    _write(data_root / "jobs" / "match_cache.json", "{}")
    _write(data_root / "applications" / "applications.json", '[{"id":"a"}]')
    _write(data_root / "source_cache" / "remoteok.json", "{}")
    _write(data_root / "settings" / "ai_settings.json", "{}")
    _write(data_root / "sources.json", "{}")

    summary = data_management.get_data_summary(data_root)
    assert summary["counts"]["cv_files"] == 3
    assert summary["counts"]["profile_saved"] is True
    assert summary["counts"]["saved_jobs"] == 2
    assert summary["counts"]["applications"] == 1
    assert summary["counts"]["cache_files"] == 2
    assert summary["counts"]["settings_files"] == 2
    assert "very private cv text" not in json.dumps(summary)


def test_clear_cache_keeps_saved_jobs_cv_profile_and_applications(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    preserved_paths = [
        data_root / "cv" / "current.pdf",
        data_root / "cv" / "profile.json",
        data_root / "jobs" / "jobs.json",
        data_root / "applications" / "applications.json",
    ]
    for path in preserved_paths:
        _write(path, "[]")
    cache_paths = [data_root / "jobs" / "match_cache.json", data_root / "source_cache" / "remoteok.json"]
    for path in cache_paths:
        _write(path, "{}")

    removed = data_management.clear_cache_files(data_root)
    assert removed == 2
    assert all(path.exists() for path in preserved_paths)
    assert all(not path.exists() for path in cache_paths)


def test_reset_preserves_templates_but_removes_all_workspace_files(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _write(data_root / "cv" / "current.pdf", "cv")
    _write(data_root / "settings" / "ai_settings.json", "{}")
    _write(data_root / "sources.json", "{}")
    _write(data_root / "cv" / "profile.example.json", "{}")
    _write(data_root / "cv" / ".gitkeep", "")

    removed = data_management.reset_workspace_data(data_root)
    assert removed == 3
    assert not (data_root / "cv" / "current.pdf").exists()
    assert not (data_root / "settings" / "ai_settings.json").exists()
    assert not (data_root / "sources.json").exists()
    assert (data_root / "cv" / "profile.example.json").exists()
    assert (data_root / "cv" / ".gitkeep").exists()


def test_reset_api_requires_exact_confirmation_and_does_not_delete_on_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "data"
    _write(data_root / "jobs" / "jobs.json", "[]")
    monkeypatch.setattr(main, "DATA_DIR", data_root)
    client = TestClient(main.app)

    response = client.post("/api/data/reset", json={"confirmation": "yes"})
    assert response.status_code == 400
    assert (data_root / "jobs" / "jobs.json").exists()


def test_reset_api_closes_browser_then_cleans_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "data"
    _write(data_root / "jobs" / "jobs.json", "[]")
    _write(data_root / "cv" / "profile.json", "{}")
    _write(data_root / "cv" / "profile.example.json", "{}")
    monkeypatch.setattr(main, "DATA_DIR", data_root)
    calls = {"closed": False}

    async def close_browser() -> dict[str, object]:
        calls["closed"] = True
        return {"success": True}

    monkeypatch.setattr(main, "close_browser_session", close_browser)
    client = TestClient(main.app)
    response = client.post("/api/data/reset", json={"confirmation": "DELETE ALL LOCAL DATA"})
    assert response.status_code == 200
    assert calls["closed"] is True
    assert not (data_root / "jobs" / "jobs.json").exists()
    assert not (data_root / "cv" / "profile.json").exists()
    assert (data_root / "cv" / "profile.example.json").exists()
    assert response.json()["counts"]["total_data_files"] == 0


def test_browser_error_messages_separate_missing_binary_from_navigation_failure() -> None:
    missing = _browser_failure_message(Exception("Executable doesn't exist at path"), browser_started=False)
    assert "python -m playwright install chromium" in missing
    assert "Chromium is missing" in missing

    navigation = _browser_failure_message(Exception("net::ERR_NAME_NOT_RESOLVED"), browser_started=True)
    assert "could not be loaded" in navigation
    assert "regular browser" in navigation


def test_browser_diagnostics_endpoint_returns_install_guidance() -> None:
    client = TestClient(main.app)
    response = client.get("/api/browser/diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "playwright_installed" in payload
    assert "chromium_installed" in payload
    assert payload["install_command"] == "python -m playwright install chromium"
