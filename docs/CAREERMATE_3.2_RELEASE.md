# CareerMate 3.2 — Navigation and portal registry update

## Sidebar navigation

- The expanded desktop sidebar's navigation list is independently scrollable.
- The profile-readiness and provider-status footer stays fixed below the navigation list and no longer overlays the final navigation links.
- On short desktop viewports, navigation rows compact slightly and the list scrolls; links are not removed.
- Touch devices retain the existing bottom navigation and More sheet.
- The **Today** item is the Overview view rendered by `TodayDashboard`; the brand/home action also opens it.

## Portal configuration document

- Active portal registry: `data/sources.json` (local and git-ignored).
- Safe sample template: `data/portals.example.json` (all providers disabled; placeholder data only).
- Each employer entry supports `career_url`, `jobs_url`, and `notes` in addition to provider-specific ATS identifiers.
- URL metadata must use public HTTPS URLs. API secrets must not be stored in JSON.
- For a new setup, copy `data/portals.example.json` to `data/sources.json`.
- For an existing setup, back up `data/sources.json` and merge optional fields. Do not overwrite the existing company watchlist.

See `docs/PORTAL-CONFIGURATION.md` and `docs/SIDEBAR-NAVIGATION.md` for details.

## Verification

- Backend tests: 26 passed.
- FastAPI application import: passed (`CareerMate API`, version 3.2.0).
- Python bytecode compilation: passed.
- Portal sample validation: 10 provider sections / 10 disabled examples passed.
- TypeScript/TSX syntax transpilation: 15 files, zero syntax errors.
- CSS parsing: 26 stylesheets, zero top-level parse errors.
- Full Vite production build: not run because frontend dependencies are not installed in this environment.
- Headless Chromium layout run: did not complete in this environment; verify the interactive hover/scroll behavior in the local browser after installing dependencies.
