# CareerMate 2.0 — implementation notes

CareerMate 2.0 is a local-first career workspace update. It keeps the existing job discovery, matching, CV preparation, application tracking and browser-assistance workflows while adding a new navigation shell, analytics and automation views, and a candidate evidence vault.

## What changed

- Rebuilt the application shell with grouped navigation, responsive mobile navigation, profile-readiness progress, privacy/provider context and a `Ctrl/Cmd + K` quick-navigation palette.
- Added Career Analytics using live workspace records: job count, scored-match distribution, strong matches, application funnel, interview rate and application source counts.
- Added an Automation Centre showing configured source adapters, saved-search preferences and recorded alerts. The screen distinguishes saved frequency preferences from confirmed scheduler activity.
- Added a local candidate evidence vault. Claims begin as pending; the user must explicitly mark each claim verified. Records can be added, filtered, verified, returned to pending or deleted.
- Restored four Pydantic model modules referenced by the API but missing from the supplied source archive: application, browser assistance, AI settings and data-management models.
- Added backend tests for evidence storage and API behavior.
- Added a cohesive visual system with responsive layouts, page/card transitions, focus treatments and reduced-motion support.

## Current implementation boundaries

- The evidence vault is a reviewable local source-of-truth feature. It is not yet automatically injected into the job matcher or document-generation prompts. That integration should be a later, separately tested change so verified facts can be prioritized without silently excluding facts that are merely not recorded.
- Analytics are calculated from records currently stored in the workspace. Historical time-saved metrics and trend lines are not fabricated; they need timestamped activity events before they can be calculated honestly.
- Daily and weekly saved-search frequencies are preferences for the existing scheduler. The Automation Centre does not claim that a scheduled check ran unless the backend has recorded it.
- Application form coverage remains site-dependent. Browser assistance should not bypass authentication, MFA, CAPTCHAs, anti-bot restrictions or access controls. Final submission remains an explicit user action.
- The supplied archive did not contain the four model files imported by `backend/app/main.py`. Restored schemas are covered by the current test suite, but compare these files with the source repository before replacing a fuller local copy.
- A full normalized SQLite migration, recruiter CRM, interview-story bank, MCP server and broader ATS handler catalogue are not included in this release. They remain candidates for future milestones rather than partially implemented features.

## Run locally

### Backend

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. For the Docker setup, copy `backend/.env.example` to `backend/.env`, then run `docker compose up --build` from the repository root.

## Verification performed for this package

- Backend test suite: **144 passed**.
- Python bytecode compilation: performed as a separate validation step.
- Frontend: TS/TSX syntax is checked with the TypeScript transpiler. A full `npm run build` is dependent on the npm packages declared in `frontend/package-lock.json`; the build environment used to prepare this package could not complete package installation because npm registry DNS resolution was unavailable. Run `npm ci` and `npm run build` on a machine with npm registry access before treating the frontend bundle as production-verified.
