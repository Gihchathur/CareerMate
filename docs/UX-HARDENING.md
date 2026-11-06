# CareerMate UX hardening (2.2.0)

## Screenshot-based UX audit

The `docs/previews/` folder contains a hover-first navigation fixture, rendered collapsed/expanded desktop previews and a phone layout preview. They use the actual CareerMate stylesheets with representative sample content; they are visual references, not a live app session or real job data. Desktop references: `careermate-2.2-nav-collapsed.png` and `careermate-2.2-nav-expanded.png`. Phone reference: `careermate-2.2-nav-mobile.png`.

> **2.2.0 interaction update:** The desktop navigation no longer uses a click-triggered menu. The icon rail expands automatically on pointer entry and contracts on pointer exit. It also expands on keyboard focus, while Escape can collapse it. There is no desktop menu toggle button. Touch layouts use the bottom navigation and an all-sections sheet. The expanded navigation animates the workspace grid from the compact rail width to the expanded panel width. The main canvas shifts smoothly to make room rather than sitting underneath the menu; when the pointer leaves for the canvas, the rail contracts and the canvas returns.

## 2.2.0 UX review and changes

The 2.2 pass focuses on the full workspace rather than discovery alone:

- **Navigation:** hover-first expansion, keyboard-focus fallback, no desktop toggle control, semantic SVG line icons, active-route glow and a visible teal route indicator.
- **Short viewports:** condensed group spacing at shorter heights so the expanded panel fits without becoming a second vertical scroll container.
- **Canvas:** subtle aurora lighting and drafting-grid texture are confined to the page background. Content cards remain mostly opaque and calm instead of turning every component into a glass panel.
- **Content hierarchy:** shared page headers, panels, form fields, helper text, buttons and tables receive consistent spacing, readable contrast and responsive layout behavior.
- **Discovery:** job cards keep employer mark, job information and actions in separate grid columns; dates cannot push controls over the job text. Branded source marks remain next to the source label.
- **Other sections:** application, browser-assistance, profile/evidence, platform configuration, settings, analytics and automation surfaces receive text, grid and overflow refinements. Portalled job and match detail drawers are hardened separately because they render outside the main content frame.
- **Accessibility:** pointer hover is not the only way to expand the desktop rail. Keyboard focus expands it, nav items remain real buttons with accessible names and current-page semantics, visible focus rings are preserved, and reduced-motion preferences are respected.

## Interaction design reference

- [shadcn/ui Sidebar](https://ui.shadcn.com/docs/components/sidebar): reference for grouped navigation structure, icon-only rail patterns and consistent sidebar anatomy. CareerMate uses the compact rail as a hover target rather than adopting a click-based collapse trigger.
- [Radix UI Hover Card](https://www.radix-ui.com/primitives/docs/components/hover-card): reference for delayed/intentional hover surfaces. Its documentation notes that hover-only interaction does not serve keyboard users by itself, so CareerMate also expands on focus and provides a touch-specific navigation pattern.


The supplied screenshots exposed several issues that made the workspace feel cramped and fragile:

1. **Navigation consumed too much horizontal space.** The full-width sidebar remained visible on every page and could scroll independently. On shorter screens it competed with the page for vertical space.
2. **The discovery page had unstable density.** The filter panel and job feed competed for width. The search controls could wrap awkwardly, while the saved-search row used three columns that did not gracefully collapse.
3. **Job cards relied on a fragile flex row.** Long dates, action buttons and job metadata competed for the same line. Small viewports could make the action group squeeze the description or overflow.
4. **Typography was too small and low contrast.** Many labels, hints and metadata used 7–10px type and pale gray colors. This made important information difficult to scan.
5. **Source identity was hidden in plain text.** A source name alone did not provide the quick visual recognition expected from a multi-source job feed.
6. **The page had insufficient responsive hierarchy.** A desktop two-column search should become a stacked tablet/mobile workflow, not a compressed desktop layout.

## Changes made

### Navigation model

- Desktop uses a 76px icon rail that expands to a responsive 238–286px panel (depending on viewport width). It does not have its own vertical scrollbar.
- Icons navigate directly to frequently used sections and show the active page state.
- Tooltips reveal labels without taking permanent canvas width.
- Pointer entry automatically expands the rail into a grouped side panel with descriptions, counts and active-page context. Pointer exit collapses it to icons. The workspace grid animates to reserve the panel width, preventing the expanded menu from obscuring page content. Keyboard focus expands it as an accessible alternative; Escape can collapse it. Pointer-driven focus does not pin the menu open after the mouse leaves.
- On phones and touch-first tablets, a compact bottom bar provides common destinations and a modal sheet exposes all sections. Touch-first tablet rules explicitly override the legacy desktop hide rule so the bottom bar remains visible.

### Discovery and job cards

- Discovery now uses a bounded filter column and a flexible results column on desktop.
- Tablet layouts stack filters above results and arrange fields into a two-column form where space permits.
- Mobile layouts stack the form and results, while card actions move to a dedicated row.
- Job cards use a CSS grid with dedicated columns for employer monogram, job information and actions.
- Long dates are bounded and ellipsized instead of pushing buttons off-screen.
- Saved-search controls collapse to two columns and then one column as width decreases.
- Job source marks are shown next to the source label. LinkedIn, Indeed, Glassdoor, JobTech, Remote OK, Arbeitnow and common ATS marks are recognized from the source ID and, where applicable, the listing URL. Unknown sources use a generic fallback.

### Readability and motion

- Increased the type scale and contrast for the page title, job title, company/location metadata, field labels, helper copy, result counts and action controls.
- Kept color roles semantic: violet for primary actions, teal for positive/active states, amber for warnings and slate for neutral information.
- Added short, purposeful transitions to the rail, workspace grid and menu actions.
- The reduced-motion preference disables navigation and page entrance transitions.
- Focus-visible rings, accessible names and native button semantics are retained for keyboard and assistive-technology users.

## Design references reviewed

The changes borrow patterns, not application code, from:

- [JobNavigator](https://github.com/vesaias/JobNavigator): its token-based component system, keyboard-first job feed, advanced filters, split-detail workflows and grouped themes are good references for a maintainable job-search workspace. Its 2.0 changelog describes composing screens from reusable semantic primitives and keeping job analysis visible as background operations run.
- [shadcn job-application Kanban block](https://www.shadcn.io/blocks/kanban-job-applications): a useful reference for a compact application pipeline, detail dialogs and motion-aware interactions.
- [Motion for React](https://motion.dev/): a reference for future page-level transitions and list-layout animations. This UX pass deliberately avoids adding another runtime dependency until package installation and the production build can be verified in the target environment.

The current implementation remains dependency-light and uses the existing React/TypeScript frontend and CSS tokens. This reduces upgrade risk while creating a clearer path to component extraction and a richer motion system.

## Next UX improvements

These are intentionally not represented as completed in this release:

- Add a user-selectable results layout (comfortable cards / compact table) and density preference.
- Add job sorting for date, match score, company and source.
- Add saved filter presets and source chips with enable/disable actions.
- Add a job detail side panel that preserves list position and supports keyboard next/previous navigation.
- Add list virtualization only when measured result volume justifies it.
- Add a theme system (light, dark, system) using semantic design tokens rather than scattered color overrides.
- Complete visual regression tests at 360px, 768px, 1024px, 1280px and 1440px widths.

## Verification notes

- Backend tests: run with `PYTHONPATH=backend python -m pytest -q` from the repository root.
- TypeScript/React production build: run `npm ci && npm run build` inside `frontend/`.
- The hover fixture was rendered in Chromium at 1440, 1280, 1024, 900, 768, 760, 430, 390, 360 and 320px widths. No horizontal document overflow was detected. The test confirmed that the rail expands from 76px to the responsive expanded width (286px at 1440px), remains expanded while the pointer is over the panel, and contracts when the pointer enters the shifted canvas. Keyboard focus expansion was also checked. Short desktop heights (900, 800, 768, 700, 640 and 600px) were checked to ensure the expanded navigation fits without an inner rail scrollbar. Touch-first tablet navigation was tested at 820px with coarse-pointer emulation. This fixture uses the repository stylesheets and representative sample content; it is not a live React session.
- TypeScript/TSX syntax parsing and CSS parsing passed. The backend suite passed 144 tests.
- A production frontend build and live React browser session could not be verified: `npm ci --prefer-offline --no-audit --no-fund` did not complete in this environment. Run `npm ci && npm run build` inside `frontend/` locally. Do not treat syntax parsing or the static fixture as a replacement for the production build.
