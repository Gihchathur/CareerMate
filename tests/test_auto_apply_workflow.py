"""Regression tests for the reviewed multi-step application assistant."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models.browser_assistance import BrowserNavigationRequest, BrowserPageSelectRequest, BrowserSuggestionRequest
from app.services import browser_assistance


def test_navigation_request_accepts_only_supported_step_intents():
    assert BrowserNavigationRequest.model_validate({"intent": "apply"}).intent == "apply"
    assert BrowserNavigationRequest.model_validate({"intent": "continue"}).intent == "continue"
    with pytest.raises(Exception):
        BrowserNavigationRequest.model_validate({"intent": "submit"})


def test_browser_page_selection_request_bounds_tab_index():
    assert BrowserPageSelectRequest.model_validate({"page_index": 0}).page_index == 0
    with pytest.raises(Exception):
        BrowserPageSelectRequest.model_validate({"page_index": -1})
    with pytest.raises(Exception):
        BrowserPageSelectRequest.model_validate({"page_index": 31})


def test_newly_opened_loaded_tab_becomes_active_automatically():
    class Page:
        def __init__(self, url):
            self.url = url
        def is_closed(self):
            return False

    class Context:
        def __init__(self, pages):
            self.pages = pages

    async def run():
        original, popup = Page("https://company.example/jobs/123"), Page("https://ats.example/apply/123")
        session = browser_assistance.ActiveBrowserSession(
            playwright=None, browser=None, context=Context([original, popup]), page=original,
            application_id="application:test", known_pages=[original],
        )
        await browser_assistance._synchronize_active_page(session)
        assert session.page is popup
        assert popup in session.known_pages

    asyncio.run(run())


def test_open_blank_popup_does_not_steal_active_page_until_it_loads():
    class Page:
        def __init__(self, url): self.url = url
        def is_closed(self): return False
    class Context:
        def __init__(self, pages): self.pages = pages

    async def run():
        original, popup = Page("https://company.example/jobs/123"), Page("about:blank")
        session = browser_assistance.ActiveBrowserSession(
            playwright=None, browser=None, context=Context([original, popup]), page=original,
            application_id="application:test", known_pages=[original],
        )
        await browser_assistance._synchronize_active_page(session)
        assert session.page is original
        popup.url = "https://ats.example/apply/123"
        await browser_assistance._synchronize_active_page(session)
        assert session.page is popup

    asyncio.run(run())


def test_form_scanner_includes_supported_embedded_application_frames(monkeypatch):
    class FakeFrame:
        def __init__(self, url, field_label):
            self.url = url
            self.field_label = field_label

        async def evaluate(self, script, offset=0):
            if script == browser_assistance.COOKIE_DISMISS_SCRIPT:
                return {"dismissed": False, "label": ""}
            return {
                "fields": [{
                    "field_id": f"cm-field-{offset}", "label": self.field_label,
                    "kind": "text", "required": True,
                }],
                "has_apply_action": False,
                "has_continue_action": False,
                "submit_available": False,
                "title": "Test application",
            }


    class FakePage(FakeFrame):
        def __init__(self):
            super().__init__("https://careers.example.org/apply", "Candidate name")
            self.frames = [self, FakeFrame("https://ats.example.org/embed", "Relevant experience")]

        def is_closed(self): return False
        async def title(self): return "Careers"
        async def wait_for_timeout(self, _ms): return None

    class FakeContext:
        def __init__(self, page): self.pages = [page]

    async def run():
        page = FakePage()
        session = browser_assistance.ActiveBrowserSession(
            playwright=None, browser=None, context=FakeContext(page), page=page,
            application_id="application:frames", known_pages=[page],
        )
        monkeypatch.setattr(browser_assistance, "_hostname_is_public", lambda host, port: True)
        monkeypatch.setattr(browser_assistance, "_active_session", session)
        result = await browser_assistance.scan_current_form()
        assert result["field_count"] == 2
        assert result["fields"][0]["frame_index"] == 0
        assert result["fields"][1]["frame_index"] == 1
        assert [field["field_id"] for field in result["fields"]] == ["cm-field-0", "cm-field-1"]

    asyncio.run(run())


def test_suggestion_request_validates_field_ids_and_bounds_batch():
    assert BrowserSuggestionRequest.model_validate({"field_ids": ["cm-field-2"]}).field_ids == ["cm-field-2"]
    with pytest.raises(Exception):
        BrowserSuggestionRequest.model_validate({"field_ids": ["submit-button"]})
    with pytest.raises(Exception):
        BrowserSuggestionRequest.model_validate({"field_ids": []})


def test_field_scanner_allows_cv_attachment_but_not_other_file_uploads(monkeypatch, tmp_path):
    monkeypatch.setattr(browser_assistance, "CURRENT_CV_PATH", tmp_path / "current.pdf")
    (tmp_path / "current.pdf").write_bytes(b"test-only")
    cv_field = browser_assistance._field_from_raw({
        "field_id": "cm-field-0", "label": "Upload resume / CV", "kind": "file", "required": True,
    })
    other_file = browser_assistance._field_from_raw({
        "field_id": "cm-field-1", "label": "Upload passport", "kind": "file", "required": True,
    })
    legal_checkbox = browser_assistance._field_from_raw({
        "field_id": "cm-field-2", "label": "I agree to the terms and conditions", "kind": "checkbox",
    })
    assert cv_field is not None and cv_field.suggested_key == "cv_file"
    assert other_file is None
    assert legal_checkbox is None


def test_submit_service_refuses_without_explicit_confirmation():
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="not approved"):
        asyncio.run(browser_assistance.submit_reviewed_application("application:test", False))


def test_fill_refuses_stale_review_when_browser_tab_changed(monkeypatch):
    async def fake_scan():
        return {"url": "https://ats.example.org/new-step"}

    monkeypatch.setattr(browser_assistance, "scan_current_form", fake_scan)
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="tab changed"):
        asyncio.run(browser_assistance.fill_reviewed_fields(
            "application:test", [{"field_id": "cm-field-0", "value": "candidate@example.org"}],
            expected_url="https://company.example.org/job/1",
        ))


def test_submit_service_refuses_when_reviewed_tab_has_changed(monkeypatch):
    class Page:
        url = "https://ats.example.org/another-step"
        def is_closed(self): return False

    class Context:
        pages = []

    session = browser_assistance.ActiveBrowserSession(
        playwright=None, browser=None, context=Context(), page=Page(),
        application_id="application:test", known_pages=[],
    )
    monkeypatch.setattr(browser_assistance, "_active_session", session)
    with pytest.raises(browser_assistance.BrowserAssistanceError, match="tab changed"):
        asyncio.run(browser_assistance.submit_reviewed_application(
            "application:test", True, expected_url="https://ats.example.org/review",
        ))


def test_advance_endpoint_delegates_only_the_requested_safe_intent(monkeypatch):
    async def fake_advance(application_id, intent):
        return {"success": True, "application_id": application_id, "intent": intent}

    monkeypatch.setattr(main, "advance_application_step", fake_advance)
    client = TestClient(main.app)
    response = client.post("/api/applications/application:test/browser/advance", json={"intent": "apply"})
    assert response.status_code == 200
    assert response.json()["intent"] == "apply"


def test_select_page_endpoint_delegates_index(monkeypatch):
    async def fake_select(application_id, page_index):
        return {"success": True, "application_id": application_id, "active_page_index": page_index}

    monkeypatch.setattr(main, "select_browser_page", fake_select)
    response = TestClient(main.app).post(
        "/api/applications/application:test/browser/select-page", json={"page_index": 1},
    )
    assert response.status_code == 200
    assert response.json()["active_page_index"] == 1


def test_submit_endpoint_never_calls_browser_when_user_did_not_approve(monkeypatch):
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("The service must not be called when submission has not been approved.")

    monkeypatch.setattr(main, "submit_reviewed_application", should_not_run)
    response = TestClient(main.app).post(
        "/api/applications/application:test/browser/submit",
        json={"confirm_submission": False},
    )
    assert response.status_code == 409
    assert "not approved" in response.json()["detail"].casefold()
