from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"


def test_frontend_uses_shared_floating_select_instead_of_native_selects():
    native_selects = []
    for source in FRONTEND_SRC.rglob("*.tsx"):
        if re.search(r"<select\b", source.read_text(encoding="utf-8")):
            native_selects.append(str(source.relative_to(ROOT)))
    assert native_selects == []

    component = (FRONTEND_SRC / "components" / "ui" / "FloatingSelect.tsx").read_text(encoding="utf-8")
    assert "createPortal" in component
    assert "document.body" in component
    assert "visualViewport" in component


def test_browser_assistance_has_distinct_input_and_accepted_visual_states():
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND_SRC / "styles" / "pages" / "browser-assistance.css").read_text(encoding="utf-8")
    assert '"Needs your input"' in app
    assert '"Accepted"' in app
    assert "browser-field-status-note" in app
    assert ".browser-field-card.state-needs-input" in styles
    assert ".browser-field-card.state-accepted" in styles
    assert ".browser-field-card.state-suggested" in styles


def test_explore_uses_only_employer_portal_sources_and_has_a_portal_empty_state():
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    source_block = app.split("const SOURCE_OPTIONS", 1)[1].split("];", 1)[0]
    for public_source in ("jobtech_links", "remoteok", "arbeitnow"):
        assert public_source not in source_block
    assert "No active employer portals selected" in app
    assert "setSelectedSources(enabledPortalSourceIds" in app

def test_match_insight_action_is_inside_a_dedicated_actions_container():
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND_SRC / "quality-fixes.css").read_text(encoding="utf-8")
    assert "match-job-option-actions" in app
    assert ".match-job-option-actions" in styles
    assert "grid-template-columns: minmax(0, 1fr) auto" in styles

def test_careermate_uses_exact_tailored_pdf_filename_for_ats_uploads():
    app = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    api = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")
    assert "__CAREERMATE_TAILORED_CV__" in app
    assert "pdf_filename" in app
    assert "attached_files" in api
    assert "Original uploaded CV · current.pdf" in app
    assert "CV document to attach" in app
    assert "The attached PDF keeps this name" in app
