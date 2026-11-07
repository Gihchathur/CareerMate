# CareerMate portal-first Explore update

## What changed

- Redesigned Explore to follow the supplied dashboard reference: lavender/white surfaces, purple accents, a compact filter column, portal selection, result tabs, sorting and list/grid controls.
- Replaced Explore's generic job-source selector with a company-level Portals list. Each checkbox represents one configured employer board, even when multiple companies use the same ATS provider.
- Search requests now include the exact selected company portal IDs. The backend filters the configured employer boards by those IDs before fetching jobs.
- Saved searches retain their selected portal IDs. Manual and scheduled checks reuse the same company selection. Legacy saved searches without portal IDs are not allowed to silently fall back to searching all employer boards.
- Removed the old Discovery sources / external search shortcuts panel from portal management. Settings, Inbox and Scheduled Scans now use portal-first language and present employer ATS adapters rather than public-feed shortcuts.
- Updated `.gitignore` so Python model source files under `backend/app/models/` are not hidden by the broad `models/` ignore rule.

## Validation performed

- `python -m compileall -q backend/app` passed.
- Focused regression tests: **19 passed, 1 deselected**.
- TypeScript/TSX parser check: **16 files parsed, no syntax errors**.

## Important source-archive limitation

The supplied archive is missing modules imported directly by `backend/app/main.py`:

- `backend/app/models/candidate_evidence.py`
- `backend/app/models/application.py`
- `backend/app/models/browser_assistance.py`
- `backend/app/models/ai.py`
- `backend/app/models/data_management.py`
- `backend/app/models/workflow.py`

Because those files are absent, the complete backend test suite cannot collect and the API cannot be confirmed to start from this archive. Restore those modules from the full working repository before running the complete application. They were not replaced with guessed placeholders.

The frontend dependencies also could not be fully installed in the available environment, so a production Vite build and browser-level visual verification were not completed. The source syntax check did pass.

## Exact Explore reference dashboard update

The latest Explore screen has been aligned much more closely to the supplied 1672 × 941 reference:

- Full-height 260px dark navigation rail with CareerMate branding, grouped navigation, a glowing purple active state, badges, and candidate profile completion at the bottom.
- A 64px top bar positioned to the right of the navigation rail, with workspace breadcrumb, command search, AI/privacy state, notifications, and profile shortcut.
- Lavender/white Explore canvas with the reference's compact 312px search-and-portals column, result tabs, sort/list-grid controls, and compact opportunity rows.
- Company portal selection remains at the company-board level. ATS provider names are shown as secondary metadata, not as the selection unit.
- The lower CV tailoring card is connected to the selected/first visible job and the existing CV tailoring API. The application questions card reflects the active browser form session and its actual fields; when no session is open it shows a useful Pipeline link instead of invented sample answers.
- Company accent treatments follow company identity rather than result row position, so sorting does not shuffle the colors.
- Responsive behavior keeps the existing mobile bottom navigation and stacks the Explore panels on narrower viewports.

### Latest validation

- TypeScript/TSX parser validation passed for `App.tsx`, `WorkspaceShell.tsx`, and `Icon.tsx`.
- CSS brace-balance check passed for `reference-dashboard.css`.
- Python backend compilation passed.
- Focused job-search and portal-health checks: **19 passed**. The additional starter-portal API test remains blocked because the original supplied archive does not contain `backend/app/models/candidate_evidence.py` (and the other missing backend model files listed above), which `backend/app/main.py` imports.
- A full frontend type-check/build could not run because the installed `frontend/node_modules` lacks `vite/client` and Node type definitions. The project ZIP excludes this incomplete `node_modules` directory so dependencies can be restored cleanly with `npm ci`.
- No browser-rendered screenshot comparison was possible in this environment. The CSS/layout is authored against the supplied reference dimensions, but a local browser pass is still recommended after dependencies and the missing model files are restored.
