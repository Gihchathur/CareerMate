"""First-run and upgrade seeding for CareerMate's monitored employer portals."""

import json
from pathlib import Path

from app.services import job_search


def _configure_paths(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(job_search, "SOURCE_CONFIG_PATH", data_dir / "sources.json")
    monkeypatch.setattr(job_search, "STARTER_CONFIG_PATH", Path(__file__).resolve().parents[2] / "data" / "sources.example.json")
    monkeypatch.setattr(job_search, "STARTER_SEED_MARKER_PATH", data_dir / "settings" / "portal-starter-seeded.json")


def _all_boards(config):
    return [(provider, board) for provider, boards in config.items() for board in boards]


def test_first_run_seeds_five_enabled_starter_portals(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)

    config = job_search.load_source_config()
    boards = _all_boards(config)

    assert len(boards) == 5
    assert {board["company"] for _, board in boards} == {
        "Spotify", "Vercel", "Lovable", "Legora", "Temporal"
    }
    assert all(board["enabled"] is True for _, board in boards)
    assert all(board["starter_sample"] is True for _, board in boards)
    assert job_search.STARTER_SEED_MARKER_PATH.is_file()
    persisted = json.loads(job_search.SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    assert len(_all_boards(persisted)) == 5


def test_upgrade_from_previous_seed_marker_adds_missing_samples_non_destructively(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    job_search.SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.SOURCE_CONFIG_PATH.write_text(json.dumps({
        "greenhouse": [{"enabled": True, "board_token": "custom-board", "company": "My Company"}],
        "lever": [], "teamtailor": [], "ashby": [], "smartrecruiters": [],
        "workable": [], "recruitee": [], "breezy": [], "personio": [], "workday": [],
    }), encoding="utf-8")
    job_search.STARTER_SEED_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.STARTER_SEED_MARKER_PATH.write_text(
        json.dumps({"initialized": True, "starter_portals_version": 2}), encoding="utf-8"
    )

    config = job_search.load_source_config()
    all_boards = _all_boards(config)
    assert len(all_boards) == 6
    assert any(board.get("board_token") == "custom-board" for provider, board in all_boards if provider == "greenhouse")
    assert {board["company"] for _, board in all_boards if board.get("starter_sample")} == {
        "Spotify", "Vercel", "Lovable", "Legora", "Temporal"
    }
    marker = json.loads(job_search.STARTER_SEED_MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["starter_portals_version"] == job_search.STARTER_PORTALS_VERSION



def test_upgrade_from_v2_empty_registry_seeds_five_portals(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    job_search.SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.SOURCE_CONFIG_PATH.write_text(
        json.dumps({provider: [] for provider in job_search.SUPPORTED_ATS}), encoding="utf-8"
    )
    job_search.STARTER_SEED_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.STARTER_SEED_MARKER_PATH.write_text(
        json.dumps({"initialized": True, "starter_portals_version": 2}), encoding="utf-8"
    )

    config = job_search.load_source_config()

    assert len(_all_boards(config)) == 5
    assert {board["company"] for _, board in _all_boards(config)} == {
        "Spotify", "Vercel", "Lovable", "Legora", "Temporal"
    }
    marker = json.loads(job_search.STARTER_SEED_MARKER_PATH.read_text(encoding="utf-8"))
    assert marker["starter_portals_version"] == 3

def test_starter_seed_runs_once_and_does_not_restore_removed_portals(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    first = job_search.load_source_config()
    assert len(_all_boards(first)) == 5

    empty = {provider: [] for provider in job_search.SUPPORTED_ATS}
    job_search.save_source_config(empty)
    second = job_search.load_source_config()
    assert len(_all_boards(second)) == 0


def test_existing_duplicate_starter_identifier_is_not_duplicated(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    job_search.SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.SOURCE_CONFIG_PATH.write_text(json.dumps({
        "greenhouse": [{"enabled": False, "board_token": "vercel", "company": "My Vercel entry", "notes": "User's own note"}],
    }), encoding="utf-8")

    config = job_search.load_source_config()
    greenhouse = config["greenhouse"]
    assert len(greenhouse) == 1
    assert greenhouse[0]["company"] == "My Vercel entry"
    assert greenhouse[0]["notes"] == "User's own note"
    assert sum(len(items) for items in config.values()) == 5


def test_starter_sample_flag_must_be_boolean():
    from app.services.job_sources.base import JobSourceError
    import pytest

    with pytest.raises(JobSourceError):
        job_search.validate_source_config({
            "greenhouse": [{"enabled": False, "board_token": "demo", "starter_sample": "yes"}]
        })


def test_missing_registry_is_recreated_from_starters_even_if_marker_exists(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    job_search.STARTER_SEED_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    job_search.STARTER_SEED_MARKER_PATH.write_text(
        json.dumps({"initialized": True, "starter_portals_version": 2}), encoding="utf-8"
    )

    config = job_search.load_source_config()
    assert len(_all_boards(config)) == 5
    assert job_search.SOURCE_CONFIG_PATH.is_file()


def test_source_config_api_returns_starter_portals_on_first_load(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    from app.main import get_job_source_config

    response = get_job_source_config()
    assert response["success"] is True
    boards = _all_boards(response["config"])
    assert len(boards) == 5
    assert {board["company"] for _, board in boards} == {
        "Spotify", "Vercel", "Lovable", "Legora", "Temporal"
    }
