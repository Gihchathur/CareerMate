from app.services import job_discovery


def test_custom_country_is_allowed_with_global_source(monkeypatch):
    monkeypatch.setattr(job_discovery, "fetch_remote_jobs", lambda: [])
    result = job_discovery.search_multiple_roles(
        roles=["Software Engineer"], country="Japan", city="Tokyo",
        work_mode="any", limit=10, offset=0, sources=["remoteok"],
    )
    assert result["country"] == "Japan"
    assert result["returned"] == 0


def test_jobtech_is_skipped_with_warning_outside_sweden(monkeypatch):
    monkeypatch.setattr(
        job_discovery, "search_jobs",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("JobTech must not be queried outside Sweden")),
    )
    monkeypatch.setattr(job_discovery, "fetch_remote_jobs", lambda: [])
    result = job_discovery.search_multiple_roles(
        roles=["Platform Engineer"], country="Japan", city="Tokyo",
        work_mode="any", limit=10, offset=0, sources=["jobtech_links", "remoteok"],
    )
    assert any("Sweden-focused" in warning for warning in result["warnings"])


def test_headless_browser_mode_is_opt_in(monkeypatch):
    from app.services import browser_assistance

    monkeypatch.delenv("CAREERMATE_BROWSER_HEADLESS", raising=False)
    assert browser_assistance._browser_headless_mode() is False
    monkeypatch.setenv("CAREERMATE_BROWSER_HEADLESS", "1")
    assert browser_assistance._browser_headless_mode() is True
