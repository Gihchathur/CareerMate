# CareerMate 3.1 — Portal directory and workspace UX

## What changed

The Portals page is now organized around monitored employer career boards, rather than mixing employer boards, global public feeds, and external search shortcuts in one configuration surface.

### Main Portals experience

- Employer directory sorted with enabled boards first and company names alphabetically.
- Company search across employer name, ATS domain, provider and country.
- All, Active, Paused and Attention filters.
- Company monograms with a smaller ATS provider mark (actual company logos are not inferred from company names).
- Clear Live, Live · no jobs, Paused, Needs setup, Unreachable and Not checked states.
- Public ATS health-check action and summary counts.
- Per-employer enable/pause control and Manage editor.
- Summary counts derive from currently enabled boards, so disabling a previously healthy board immediately displays Paused and excludes it from the live/empty/attention totals.

### Secondary configuration

- Add an employer portal keeps the existing supported ATS configuration controls.
- Discovery sources contains the public/global feeds and the existing ATS source selectors.
- External search shortcuts (including LinkedIn, Indeed and Glassdoor) are retained under Discovery sources. They remain external search shortcuts; they are not represented as automatically imported feeds.
- The existing AI provider configuration and environment-based credentials remain unchanged.

## Shared UX polish

- Standardized page heading and description hierarchy across the workspace.
- Improved section spacing and content readability.
- Reduced oversized/empty settings card treatment.
- Preserved the hover-first desktop navigation and the existing mobile navigation.
- Added responsive portal list layouts, with no horizontal overflow in the included desktop (1440px) and mobile (390px) fixtures.

## Visual review

Open `docs/previews/portals-ux-preview.html` after extracting the repository. The fixture uses the actual CareerMate stylesheets in their application import order and representative portal data. It is a visual review fixture, not a running React application.

Rendered screenshots are supplied alongside the release as `CareerMate-3.1-Portals-Preview.png` and `CareerMate-3.1-Portals-Mobile-Preview.png`.

## Verification performed

- Backend tests: 155 passed.
- FastAPI application import: passed.
- Python test collection and execution: passed.
- TypeScript/TSX syntax transpilation: 15 files, no syntax errors.
- CSS parser: 25 stylesheets, no parse errors.
- Icon registry check: all referenced icon names exist.
- Chromium layout fixture: no horizontal document overflow at 1440px desktop or 390px mobile widths.

A complete Vite production build was not run because `npm ci` timed out in this environment. Run `npm ci` and `npm run build` locally to complete the frontend production verification.
