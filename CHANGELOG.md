# Changelog

## 2.3.0 — Visual clarity and layout hardening

- Added a dedicated final readability layer for consistent page typography and visual hierarchy.
- Rebuilt integrated job-source tiles as responsive checkbox/brand/copy/status grids to prevent narrow-column word wrapping.
- Added recognizable source marks to integrated sources, external shortcuts, and the quick external-site selector.
- Prevented external job-site labels and availability states from breaking into vertical text.
- Rebalanced the settings hub cards and four-step workflow so text size matches card space.
- Improved candidate-profile field widths and grouped long-form project information into a full-width editor row.
- Increased label, helper, summary and status contrast across discovery, profile, settings, applications and analytics surfaces.
- Preserved the existing hover-first navigation behaviour.


## 2.2.0 — Hover-first navigation and workspace UX refinement

- Replaced the desktop click-to-open navigation popover with a true hover/focus-expanding side rail. Moving the pointer into the 76px icon rail expands the navigation horizontally and smoothly reserves the panel width in the workspace grid; leaving the navigation surface collapses it back to icons. No desktop collapse/reopen button is shown.
- Added keyboard-focus expansion and Escape handling so the hover-first interaction is not pointer-only. Touch devices use the mobile bottom bar and all-sections sheet because touchscreens do not have hover.
- Refined the navigation with a consistent inline SVG line-icon set, active-page glow, teal edge indicator, count badges, compact tooltips and restrained aurora lighting.
- Added short-viewport sizing rules so the expanded rail fits without introducing a permanent nested navigation scrollbar.
- Added low-key aurora/grid background treatment and consistent page hierarchy, spacing, readable secondary text, resilient grids, form focus states and overflow-safe content.
- Hardened portalled job/match drawers, browser-assistance panels, application records, platform settings and evidence views against clipping, squeezed text and overlapping actions.
- Preserved source-branded job marks (including the official LinkedIn mark) in opportunity cards and connector rows.
- Added reduced-motion and keyboard-focus accommodations.
- Kept job search, matching, application preparation, evidence storage and backend contracts unchanged.

## 2.1.0 — UX hardening and compact navigation

- Replaced the tall, independently scrolling desktop sidebar with a compact icon rail and an anchored grouped navigation popover.
- Added accessible tooltips, current-page indicators, count badges, Escape-to-close behavior, outside-click dismissal, and a mobile all-sections menu.
- Reworked the discovery layout for a stable filter/results grid with tablet and mobile breakpoints.
- Increased contrast and type sizes for job titles, company/location metadata, form labels, helper text, source labels and result counts.
- Hardened job cards with a grid layout, bounded date labels, non-overlapping actions, and responsive action placement.
- Added recognizable source marks for LinkedIn, Indeed, Glassdoor, JobTech, Remote OK, Arbeitnow, Greenhouse, Lever and Teamtailor, with a generic fallback. Source marks are derived from the canonical source ID and listing URL.
- Added reduced-motion handling for the new navigation interactions.
- Kept the existing search, matching, saved-search and application workflows intact.


## 2.0.0 — CareerMate Personal OS

- Rebuilt the workspace shell with grouped navigation, contextual page headers, responsive mobile navigation, profile-readiness progress and a keyboard-driven command palette with arrow-key and Enter support.
- Added Career Analytics based on actual workspace records, including match-score distribution, application funnel, interview rate and application sources.
- Added an Automation Centre for connector configuration, saved-search preferences and discovery alerts. The UI distinguishes scheduled preferences from confirmed background execution.
- Added a local Candidate Evidence Vault with validated CRUD APIs, source references, pending/verified states and explicit user-controlled verification.
- Restored four Pydantic model modules referenced by the backend API but missing from the supplied ZIP archive.
- Added storage and API tests for candidate evidence, including corrupted-data handling.
- Introduced the CareerMate 2.0 visual system, responsive layout, interaction states, animations and reduced-motion support.
- Updated frontend and API version metadata to 2.0.0.
- Preserved existing job discovery, matching, CV preparation, application tracking and browser-assistance flows.

## 5.0.0 — Fresh frontend experience rebuild

- Replaced the previous theme layers with a single, organized frontend style system.
- Rebuilt the application shell and navigation. Desktop uses a light, grouped navigation rail; mobile uses a wrapping tab grid with no nested vertical navigation scroll.
- Made the document the only page-level vertical scroll container. Removed duplicated modal scroll-lock effects that could leave the page stuck after a dialog closed.
- Moved job details, match insights, and destructive confirmation dialogs to React portals attached to the document body.
- Centralized job and match dialog keyboard handling, focus containment, focus restoration, Escape behavior, and body scroll locking. Added matching accessibility behavior to the reset confirmation dialog.
- Reworked navigation, panels, forms, job rows, requirement evidence, modal surfaces, responsive grids, typography, and motion.
- Improved content readability by replacing miniature 8–10px body text with more legible sizes across the workspace.
- Preserved the existing backend, API contracts, local JSON storage, and product workflows.

## 4.0.0 — Frontend architecture and experience rebuild

- Replaced the accumulated frontend stylesheets with a clean design system split into tokens, layout, shared components, and page patterns.
- Extracted the application shell and primary navigation into a dedicated React layout component.
- Rebuilt desktop navigation as a grouped sticky rail and mobile navigation as a horizontal tab bar.
- Removed nested page-level vertical scrolling: the document is the primary scroll container; only dialogs and intentionally scrollable content regions own their scroll.
- Reworked page surfaces, typography, form controls, job rows, metric cards, empty states, status indicators, and responsive grids.
- Centered job details, match insights, and destructive confirmation dialogs with glass-style backdrops, entrance transitions, clear close controls, and dedicated scrollable dialog bodies.
- Added interaction states, accessible focus rings, reduced-motion handling, and responsive layouts.
- Preserved backend services, API client functions, and existing product workflows.

# Changelog

## 1.1.0 - 2026-10-31

### Interaction and visual system
- Reworked the application navigation into clear groups: workspace, career tools, profile, and preferences; added a direct Job Sources destination.
- Rebuilt job details as a centered, responsive modal with a fixed command header and a separately scrollable content region. The close action remains visible regardless of scroll position.
- Added Escape-to-close, focus containment, focus restoration, and background scroll locking for job and match dialogs.
- Standardised the match report dialog with the same centered modal language and persistent header.
- Added restrained page, navigation, and dialog motion using transform and opacity, with reduced-motion support.
- Refined modal content hierarchy, section surfaces, responsive behavior, keyboard focus states, and scrollbars.

### Compatibility
- Version metadata updated to 1.1.0. Existing local JSON data and API contracts are unchanged.

## 1.0.0 - 2026-10-31

### Experience redesign
- Rebuilt the visual system across overview, job discovery, match insights, applications, CV Studio, platform configuration, AI settings, and local data management.
- Introduced a compact navigation rail, consistent typography, calmer spacing, responsive layouts, refined cards, and clearer action hierarchy.
- Simplified job discovery with a compact source picker, collapsed advanced filters, concise result rows, and responsive search controls.
- Added per-search external platform selection for enabled LinkedIn, Indeed, and Glassdoor shortcuts. Users can select one external source and open only that selected source when no integrated source is selected.
- Kept the existing backend workflows and local-first data model intact.

### Compatibility
- Version metadata updated to 1.0.0.
- No database migration required.

## 0.9.1 - 2026-10-31

- Preserve project and achievement sections during CV analysis, DOCX generation, and PDF export.
- Replace broad job-description word overlap with an explicit technical and role requirement coverage estimate.
- Add a dedicated CV Studio workflow with role-specific tailoring, inline PDF preview, DOCX/PDF downloads, and version history.
- Add a Settings hub explaining AI, CV extraction, job-source, and local-data configuration.
- Simplify job-source selection and move external platform shortcuts out of the main search form.
- Present job details in a centered dialog rather than a narrow side drawer.
- Improve PDF export error reporting and server-side diagnostics.


- Expanded platform directory to 58 platforms with explicit automatic-feed versus external-shortcut distinctions.
- Added Ashby, Workday, SmartRecruiters, Workable, Recruitee, Breezy HR and Personio public ATS adapters.
- Added salary extraction, freshness and excluded-company filters.
- Added local saved searches, daily/weekly scheduler support and in-app job alert history.
- Added AI-assisted CV tailoring, three DOCX layouts, transparent ATS score breakdown and PDF export.
- Added feature-specific backend tests and setup/limitations documentation.\n- Restored missing API model modules required to import the backend entry point.\n- Added selectable-text PDF preview, export validation and generated CV version history.

# Changelog

## 0.8.0 — 2026-10-18

### Release preparation

- Added Docker Compose support for the React frontend and FastAPI backend, with persistent local JSON data.
- Added country entry and clearer warnings for the geographic and provider-specific limits of each job source.
- Added GitHub Actions checks for backend tests, frontend production build and lint, plus container builds.
- Removed personal runtime data from the release tree and consolidated setup, configuration, privacy and browser-automation guidance.
- Added a documented distinction between native visible Chromium and headless browser operation in Docker.
- Preserved the CareerMate transparent ribbon-and-star logo assets across the existing logo filenames.

### Important boundaries

- AI-generated application content must be reviewed before use.
- Application preparation and navigation support vary by employer and ATS; login, MFA, CAPTCHA and other security controls are not bypassed.
- Job source coverage depends on supported public feeds and locally configured employer boards; selecting a country does not imply universal job-site coverage.
