# Changelog

## 3.9.0 — Complete Explore inventory and fixed navigation

- Return the complete unique eligible job inventory from the selected employer portals to Explore, while retaining the page-sized `jobs` field for older API clients.
- Trust the API's selected-portal scope instead of applying a second client-side provider/portal filter that could hide confirmed results.
- Apply keyword filtering and sorting to the complete result inventory, then paginate locally so changing pages does not re-fetch or lose jobs.
- Keep company and newest sorting stable, and reset the local page when the keyword filter or page size changes.
- Make the left navigation permanently expanded and fixed; remove pointer-enter, pointer-leave and focus-driven collapse behavior.
- Show per-portal fetched/title/location/Explore counts and distinguish listings excluded by advanced filters from genuinely empty portals.
- Add an actionable empty state that clears advanced exclusions and reruns the search when portal matches exist but salary/freshness/company filters removed them.
- Keep the desktop sidebar, workspace grid and top bar aligned at intermediate desktop viewport widths.

# Changelog

## 3.8.0 — Complete employer-board retrieval and discovery diagnostics

- Changed Explore matching to use job titles rather than free-text descriptions or department labels, preventing business/customer roles from appearing only because their descriptions mention software engineers.
- Added canonical ISO country-code mapping (for example, `SE` to `Sweden`) for public ATS location metadata.
- Retained exact provider/company portal IDs on every discovered job and used those IDs as the primary frontend attribution filter.
- Added full eligible ATS inventory persistence on the first search while retaining paginated Explore rendering; scheduled scans and manual alert checks now process the complete eligible inventory rather than only the first page.
- Removed the former 500-job SmartRecruiters and 400-job Workday caps; both connectors now paginate to the provider-reported end or an explicit 10,000-job safety ceiling.
- Raised Lever pagination to a 20,000-job safety ceiling and made safety-limit hits visible as partial results. Fixed Teamtailor's documented 30-item page-size cap, follows its JSON:API `links.next` cursor / page metadata, and reports a 6,000-job safety ceiling; the previous request for 100 items could stop after the first 30.
- Corrected Ashby workplace-mode parsing: the `isRemote` flag covers both Remote and Hybrid, so CareerMate now reads `workplaceType` to distinguish them.
- Shortened public ATS cache freshness to 120 seconds by default, retained last-successful snapshots after refresh failures, and added per-job retrieval timestamps. Added a **Refresh portals** action that bypasses the short cache for a live check.
- Added per-company Explore coverage showing fetched jobs, title matches, location/work-mode eligible matches, freshness and source warnings.
- Added a consistent icon-led page heading across every workspace tab, matching the Explore header pattern.
- Added regression tests for Legora/Ashby location metadata and workplace type, title-only relevance, all-match persistence, stale snapshots, Teamtailor cursor security and pagination beyond legacy provider limits.
- Documented provider retrieval behavior, freshness, safety ceilings and the limits of public-board completeness in `docs/PORTAL-DISCOVERY-RELIABILITY.md`.

## 3.7.0 — Match insights, portal-only Explore, and exact CV attachments

- Fixed Match Intelligence job-row layout by grouping checkbox/content and score/actions into explicit layout regions; the View insight action no longer drops outside its row.
- Added a unified CareerMate gradient SVG brand mark to the top bar, navigation rail, and favicon.
- Increased sidebar icon size and strengthened the active navigation neon selector.
- Restricted Explore source choices and displayed jobs to enabled employer ATS portals configured in Portals; historical/public-feed records remain stored and legacy APIs remain compatible.
- Added an empty-state action directing users to configure active portals.
- Added role, company, and job identifiers to tailored CV generation context.
- Generated descriptive filenames containing candidate, role, company, timestamp, and template.
- Added exact PDF filenames and employer/role metadata to the tailored document registry and Documents library.
- Enabled selection of original or tailored CV PDFs during browser application preparation. Tailored CVs are matched to the application when possible, but never silently reused for a different employer.
- Browser upload uses the generated PDF's actual basename and returns the attached filename for confirmation.
- Confirmed `sectioned` as a supported CV template in the current backend contract and added a helpful version-mismatch message for old running backends.
- Added regression coverage for filename generation, PDF attachment resolution, portal-only Explore contracts, and Match Intelligence row structure.

## 3.6.1 — Application-wide floating selects and CV layout refinement

- Replaced every remaining native select in the frontend with the shared body-portalled `FloatingSelect`, including job filters, saved-search frequency, ATS portal configuration, application stages, AI provider settings, CV templates, Evidence Vault and Pipeline status controls.
- Improved dropdown collision handling against the visual viewport, including mobile keyboard/zoom viewport changes and short windows. Menus now reposition above or below the trigger and scroll internally rather than being clipped by page panels or the hover navigation transition.
- Improved application field review guidance: required unanswered fields are highlighted in amber, unreviewed suggestions in blue, user-accepted values in green, and values confirmed in the employer form have a separate filled state.
- Added plain-language guidance beneath each field state so users know what action is needed.
- Refined the structured CV preview to show the exact reference hierarchy: centered name and headline, two contact rows, Professional Summary, Technical Skills, Professional Experience, Projects, Education and Achievements.
- Added a regression test for sectioned CV section order and candidate headline preservation.

## 3.6.0 — Floating application controls and sectioned CV template

- Replaced native dropdowns in the browser-assisted application review flow with a searchable, keyboard-operable floating select rendered into `document.body`, avoiding clipping from overflow containers and the animated hover sidebar.
- Added viewport-aware placement, scroll/resize tracking, and short transition tracking so menus remain aligned while the workspace rail expands or collapses.
- Improved dropdown styling with clear selected/active states, search, option descriptions, and keyboard guidance.
- Added field-state styling for missing user input, AI/profile suggestions requiring review, manually accepted values, and values confirmed as filled in the employer form.
- Treats an explicitly selected unchecked checkbox as a valid answer; unchecked by default is still marked for user review when required.
- Added the ATS-safe Sectioned Professional CV template with clear headings, divider rules, improved spacing, and matching PDF export. The template uses paragraph rules rather than layout tables.
- Added DOCX/PDF rendering regression tests for the new CV template.


## 3.5.1 — Inbox reset clarification and freshness fixes

- Clarified that Clear caches intentionally preserves saved jobs and therefore does not empty the Job Inbox; the Data & Privacy screen now directs users to Clean everything for a full reset.
- Improved Inbox refresh behavior after workspace reset, including no-store requests, request-generation protection, and refresh on navigation to Inbox/Today.
- Increased compact navigation icons and improved group separators while preserving the no-scroll hover rail.

## 3.5.0 — Inbox freshness and navigation icon polish

- Increased collapsed/expanded rail icon size to 18px (16px on short screens and 15px only on very short utility windows).
- Improved navigation group separation with clearer compact dividers and slightly stronger section labels in expanded mode, without restoring large section gaps or a navigation scrollbar.
- Fixed stale Inbox counts after clearing workspace data by clearing in-memory workflow state as soon as reset succeeds, refreshing the Inbox/Today view on navigation, and using no-store requests for workflow data.
- Added request-generation protection so a slow pre-reset response cannot overwrite the post-reset empty Inbox.
- Added no-store response headers to the workflow Inbox and activity API endpoints.
- Added an integration regression test proving that workspace reset removes saved jobs, triage state and activity events and that the Inbox returns zero items immediately afterwards.
- Isolated ATS source registries in the automated test fixture so bundled starter portals cannot trigger unintended external network calls during tests.

## 3.4.0 — No-scroll compact navigation and starter portal upgrade

- Narrowed the collapsed desktop navigation rail to 60px and the expanded hover panel to 220–238px.
- Reworked navigation spacing around the available viewport height. All 12 destinations fit without a nested navigation scrollbar; section captions and profile decoration compress before navigation items are affected.
- Removed sidebar scrollbar presentation from the rail, surface and navigation list.
- Improved count-badge positioning in expanded navigation.
- Added starter portal seed migration version 3. Existing installs with an older version 2 marker and an empty `data/sources.json` now receive five starter employer boards without overwriting custom entries.
- Added a regression test for the version 2 empty-registry upgrade path.

## 3.3.0 — Compact navigation and starter employer portals

- Replaced the scrollable desktop navigation list with a compact no-scroll rail. All primary destinations remain visible; section labels and decorative spacing compress on shorter windows.
- Reduced desktop rail width to 64px and expanded width to approximately 226–250px.
- Added responsive sizing for 800px, 600px and 450px-and-shorter viewports without hiding navigation destinations until extremely short utility windows.
- Added five enabled starter employer boards: Spotify (Lever), Vercel (Greenhouse), Lovable, Legora and Temporal (Ashby).
- Added a versioned, additive first-run and upgrade seed. Existing user boards are preserved, duplicates are skipped, and user removals are not silently reversed after the migration marker is written.
- Added a visible Starter tag to distinguish bundled examples from user-added portals.
- Updated portal configuration documentation to distinguish the API-compatible `sources.example.json` from the human-readable `portals.example.json` reference.

## 3.2.0

- Fixed the expanded desktop navigation: the navigation list now scrolls independently while the profile/readiness footer stays visible and cannot cover the final links.
- Kept every navigation destination available on short viewports; compact sizing is used before requiring vertical scrolling.
- Confirmed the `Today` navigation item opens the Overview dashboard (`TodayDashboard`) and clarified its navigation hint.
- Documented sidebar scroll behavior, the fixed profile footer and Overview routing.
- Added optional employer `career_url`, `jobs_url`, and `notes` metadata to the local ATS portal registry.
- Added `data/portals.example.json` as a disabled, non-secret sample registry for all supported ATS providers.
- Added portal URL editing and clickable career/jobs links in the Portals workspace.
- Updated setup documentation and version metadata.

## 3.0.0 — Workflow-first career workspace (first milestone)

- Reorganized the primary navigation around the Career Ops-inspired workflow: Today, Explore, Inbox, Match intelligence, Scheduled scans, Pipeline, Follow-ups, Portals, Analytics, CV, Documents and Config. The existing hover-first icon rail and CareerMate visual identity are preserved.
- Added a dedicated discovery Inbox between job search and application tracking. Jobs persisted by a successful integrated search are refreshed into the Inbox for triage before they are promoted into the application pipeline.
- Added local job triage stages (`new`, `reviewing`, `shortlisted`, `skipped`) with validated API updates and atomic JSON persistence in `data/workflow/job_triage.json`.
- Added a bounded workflow activity ledger in `data/workflow/events.json` for discovery scans, triage changes, application creation and application stage changes.
- Added a Today dashboard with next actions, inbox/pipeline/follow-up indicators and recent workflow activity.
- Added a Pipeline board with preparation, applied, interview, offer and closed lanes while preserving the existing application detail editor and AI drafting workflow.
- Added Follow-ups and Documents workspaces using existing application records and tailored CV artifacts. These are local views; automatic email sending and fully automated cadence scheduling are not enabled in this milestone.
- Updated Explore so selected external search shortcuts (for example LinkedIn and Indeed) open alongside integrated source searches. External job sites remain user-driven shortcuts and are not scraped or automatically imported.
- Preserved the existing AI provider configuration, CV pipeline, candidate profile, Evidence Vault, job-source adapters and human approval before submission.
- Added API tests for inbox discovery, triage validation, pipeline exclusion and bounded activity history.

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

## 3.6.1 — Application-wide floating selects and CV layout refinement

- Replaced every remaining native select in the frontend with the shared body-portalled `FloatingSelect`, including job filters, saved-search frequency, ATS portal configuration, application stages, AI provider settings, CV templates, Evidence Vault and Pipeline status controls.
- Improved dropdown collision handling against the visual viewport, including mobile keyboard/zoom viewport changes and short windows. Menus now reposition above or below the trigger and scroll internally rather than being clipped by page panels or the hover navigation transition.
- Improved application field review guidance: required unanswered fields are highlighted in amber, unreviewed suggestions in blue, user-accepted values in green, and values confirmed in the employer form have a separate filled state.
- Added plain-language guidance beneath each field state so users know what action is needed.
- Refined the structured CV preview to show the exact reference hierarchy: centered name and headline, two contact rows, Professional Summary, Technical Skills, Professional Experience, Projects, Education and Achievements.
- Added a regression test for sectioned CV section order and candidate headline preservation.

## 3.4.0 — No-scroll compact navigation and starter portal upgrade

- Narrowed the collapsed desktop navigation rail to 60px and the expanded hover panel to 220–238px.
- Reworked navigation spacing around the available viewport height. All 12 destinations fit without a nested navigation scrollbar; section captions and profile decoration compress before navigation items are affected.
- Removed sidebar scrollbar presentation from the rail, surface and navigation list.
- Improved count-badge positioning in expanded navigation.
- Added starter portal seed migration version 3. Existing installs with an older version 2 marker and an empty `data/sources.json` now receive five starter employer boards without overwriting custom entries.
- Added a regression test for the version 2 empty-registry upgrade path.

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

## 3.6.1 — Application-wide floating selects and CV layout refinement

- Replaced every remaining native select in the frontend with the shared body-portalled `FloatingSelect`, including job filters, saved-search frequency, ATS portal configuration, application stages, AI provider settings, CV templates, Evidence Vault and Pipeline status controls.
- Improved dropdown collision handling against the visual viewport, including mobile keyboard/zoom viewport changes and short windows. Menus now reposition above or below the trigger and scroll internally rather than being clipped by page panels or the hover navigation transition.
- Improved application field review guidance: required unanswered fields are highlighted in amber, unreviewed suggestions in blue, user-accepted values in green, and values confirmed in the employer form have a separate filled state.
- Added plain-language guidance beneath each field state so users know what action is needed.
- Refined the structured CV preview to show the exact reference hierarchy: centered name and headline, two contact rows, Professional Summary, Technical Skills, Professional Experience, Projects, Education and Achievements.
- Added a regression test for sectioned CV section order and candidate headline preservation.

## 3.4.0 — No-scroll compact navigation and starter portal upgrade

- Narrowed the collapsed desktop navigation rail to 60px and the expanded hover panel to 220–238px.
- Reworked navigation spacing around the available viewport height. All 12 destinations fit without a nested navigation scrollbar; section captions and profile decoration compress before navigation items are affected.
- Removed sidebar scrollbar presentation from the rail, surface and navigation list.
- Improved count-badge positioning in expanded navigation.
- Added starter portal seed migration version 3. Existing installs with an older version 2 marker and an empty `data/sources.json` now receive five starter employer boards without overwriting custom entries.
- Added a regression test for the version 2 empty-registry upgrade path.

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


## CareerMate 3.1 — Portal directory and workspace UX

- Reworked Portals into a focused monitored-employer directory inspired by Career Ops.
- Added company search and All / Active / Paused / Attention filters.
- Sorted enabled employer boards first and alphabetically by company.
- Added company monograms with ATS provider marks, clear health badges, job counts, enable/pause controls and per-board management drawers.
- Added compact health summary counts that reflect currently enabled boards and do not show stale Live status after a portal is paused.
- Moved global discovery feed settings and external search shortcuts into an expandable Discovery sources section.
- Kept employer ATS configuration in a focused Add an employer portal section.
- Added shared page header, typography and section hierarchy refinements without changing the hover-first navigation rail or AI provider configuration.
- Added desktop and mobile visual review fixtures under `docs/previews/`.
