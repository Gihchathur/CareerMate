"""Regression tests for useful, CV-grounded browser answer suggestions."""
import asyncio
import json

from app.models.application import ApplicationRecord
from app.models.candidate import CandidateProfile, Experience
from app.services import browser_assistance


class _Page:
    url = "https://careers.example.org/application"

    def is_closed(self):
        return False


class _Context:
    def __init__(self, page):
        self.pages = [page]


def test_empty_first_ai_response_is_retried_with_cv_evidence(monkeypatch, tmp_path):
    async def run():
        page = _Page()
        session = browser_assistance.ActiveBrowserSession(
            playwright=None, browser=None, context=_Context(page), page=page,
            application_id="application:test-suggestion", known_pages=[page],
        )
        session.fields = {
            "cm-field-1": browser_assistance.BrowserField(
                field_id="cm-field-1", label="Why do you want to join this engineering team?",
                kind="textarea", required=True,
            ),
            "cm-field-2": browser_assistance.BrowserField(
                field_id="cm-field-2", label="What is a strong example from your career?",
                kind="textarea", required=True,
            ),
        }
        monkeypatch.setattr(browser_assistance, "_active_session", session)
        calls = []

        def fake_generate_text(prompt, **kwargs):
            calls.append(prompt)
            if len(calls) == 1:
                return json.dumps({"suggestions": []})
            return json.dumps({"suggestions": [
                {"field_id": "cm-field-1", "value": "My documented platform experience aligns with the role's reliability and delivery focus. This is a draft for me to confirm."},
                {"field_id": "cm-field-2", "value": "A strong example from my documented experience is working with Kubernetes and observability tools to improve service operations. I will add the concrete outcome that best reflects my work."},
            ]})

        monkeypatch.setattr(browser_assistance, "generate_text", fake_generate_text)
        monkeypatch.setattr(browser_assistance, "PROJECT_ROOT", tmp_path)
        cv_path = tmp_path / "data" / "cv" / "extracted_text.txt"
        cv_path.parent.mkdir(parents=True)
        cv_path.write_text("Platform engineer; Kubernetes, Prometheus and OpenTelemetry. Contact: candidate@example.com", encoding="utf-8")

        application = ApplicationRecord(
            id="application:test-suggestion", job_id="job:1", title="Platform Engineer",
            company="Example AB", job_description="Own reliable platform services and observability.",
        )
        profile = CandidateProfile(summary="Software engineer with platform experience", skills=["Kubernetes", "Prometheus"], experience=[
            Experience(job_title="Engineer", company="Example", description=["Worked with Kubernetes and observability tools"])
        ])
        result = await browser_assistance.suggest_browser_answers(
            application.id, ["cm-field-1", "cm-field-2"], application, profile, page.url,
        )
        assert len(calls) == 2
        assert "candidate@example.com" not in calls[0]
        assert "[email redacted]" in calls[0]
        assert len(result["suggestions"]) == 2
        assert all(item["value"] for item in result["suggestions"])
        assert result["unanswered_questions"] == []

    asyncio.run(run())
