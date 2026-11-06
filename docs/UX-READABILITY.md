# CareerMate 2.3 — UX readability and layout hardening

## What changed

This release addresses the screenshot issues across shared layout rules and the affected page components, rather than applying isolated one-off fixes.

### Source integrations and discovery
- Integrated source tiles now use stable columns for selection checkbox, brand mark, descriptive copy and availability state.
- Source grids use minimum card widths and auto-fit responsive columns. Status pills do not wrap, and long descriptions wrap at word boundaries.
- External LinkedIn, Indeed and Glassdoor controls are non-breaking pills with source marks.
- External platform shortcut rows now align brand mark, name, description and action as separate regions.
- The source-directory hero can wrap its refresh action below the description instead of clipping text.

### Candidate profile
- Personal and experience fields use responsive minimum widths instead of compressing many fields into a single row.
- The skills/languages/certifications/achievements fields use a two-column layout, while the projects editor spans the full width.
- Accordion headers, counters, save state and supporting text use a larger type scale and consistent icon sizing.

### Settings and workflow guidance
- Settings cards use a two-column icon/content structure, stronger headings and readable descriptions.
- Cards have more proportionate minimum heights; text no longer looks undersized relative to the panel.
- The four-step workflow uses responsive cards with clear step markers and readable descriptions.
- Overview readiness rows and metrics use stronger contrast and a more deliberate type hierarchy.

### Shared rules
- Added `frontend/src/ux-readability.css`, imported last by `main.tsx` so it supersedes older legacy rules.
- Long text wraps by word; status labels, counts and brand labels stay unbroken.
- Controls, button icons and inline marks have consistent alignment and minimum target sizes.
- Responsive rules cover desktop, tablet and mobile layouts.
- Existing hover-first sidebar behaviour is unchanged.

## Verification

- TypeScript/TSX syntax transpilation: passed.
- CSS parsing: passed for all 23 stylesheets.
- Backend tests: 144 passed using `PYTHONPATH=backend pytest -q`.
- Full Vite production build: not verified in this environment because the archive does not include installed frontend packages and the package registry is unavailable. Run `npm ci && npm run build` locally to complete that check.

## Design principles

1. Give each card a layout that matches the amount and type of information it contains.
2. Use minimum widths for readable text rather than allowing flex/grid children to collapse.
3. Keep status labels and identifiers atomic while letting explanatory content wrap naturally.
4. Use size, weight, contrast and spacing to establish hierarchy; do not rely on color alone.
5. Keep icon containers fixed-size and align them with the first line of adjacent copy.
6. Preserve responsive behaviour and reduced-motion settings.

## Static style preview

The archive includes `docs/previews/ux-review-fixture.html`, a lightweight preview of the source directory, job discovery, candidate profile and settings layouts using the same stylesheet import order as the application. It uses illustrative fixture data, not live candidate or job records. From the project root, run `python -m http.server 8000`, then open `http://localhost:8000/docs/previews/ux-review-fixture.html#platforms`. Change the final fragment to `#discover`, `#profile` or `#settings` to inspect the other layouts.
