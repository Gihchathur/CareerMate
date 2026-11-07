"""Keep unit tests independent from a locally installed Ollama Python package."""
import sys
import types

import pytest


try:
    import ollama  # noqa: F401
except ImportError:
    module = types.ModuleType("ollama")

    class UnavailableClient:
        def __init__(self, host: str):
            raise RuntimeError("Ollama is not installed in this test environment.")

    module.Client = UnavailableClient  # type: ignore[attr-defined]
    sys.modules["ollama"] = module


@pytest.fixture(autouse=True)
def isolate_local_ai_preferences(tmp_path, monkeypatch):
    """Keep tests hermetic even when run in a working tree with local AI settings."""
    try:
        from app.services import ai_provider
    except ImportError:
        return
    monkeypatch.setattr(ai_provider, "SETTINGS_PATH", tmp_path / "ai_settings.json")
    monkeypatch.setenv("CAREERMATE_AI_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CAREERMATE_OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def isolate_local_workflow_history(tmp_path, monkeypatch):
    """Keep workflow and ATS tests away from the developer's real local workspace."""
    try:
        from app.services import workflow_storage, job_search
    except ImportError:
        return
    monkeypatch.setattr(workflow_storage, "TRIAGE_PATH", tmp_path / "workflow" / "job_triage.json")
    monkeypatch.setattr(workflow_storage, "EVENTS_PATH", tmp_path / "workflow" / "events.json")
    # A checked-out CareerMate workspace may contain enabled starter employer
    # portals. Tests that do not explicitly mock a source must not contact those
    # public ATS endpoints just because the developer has configured examples.
    monkeypatch.setattr(job_search, "SOURCE_CONFIG_PATH", tmp_path / "sources.json")
    monkeypatch.setattr(job_search, "STARTER_CONFIG_PATH", tmp_path / "sources.example.json")
    monkeypatch.setattr(job_search, "STARTER_SEED_MARKER_PATH", tmp_path / "settings" / "portal-seed.json")
