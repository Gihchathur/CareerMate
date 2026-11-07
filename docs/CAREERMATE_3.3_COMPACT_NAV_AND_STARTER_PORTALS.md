# CareerMate 3.3 — Compact navigation and starter employer portals

> Historical release note. The narrower 60px collapsed rail, no-scroll spacing and version 3 portal migration are documented in [CareerMate 3.4](CAREERMATE_3.4_NAV_AND_PORTAL_STARTERS.md).

## Sidebar behavior

The desktop rail is now 64px wide while collapsed and expands to approximately 226–250px on pointer hover or keyboard focus. It has no internal scrolling container or visible scrollbar. Navigation spacing adapts to viewport height:

- Above 800px: compact group labels are shown while expanded.
- At 800px and below: group captions and decorative spacing are removed so links remain visible.
- At 600px and below: row height, logo and profile footer compact further.
- At 450px and below: the profile footer is hidden, but all 12 navigation destinations remain present.

The page itself remains the vertical scroll surface. The rail does not capture the wheel or keyboard scroll. On phones, the existing bottom-navigation pattern remains in use.

## Five starter employer portals

CareerMate 3.3 installs five configured public employer portals:

| Employer | ATS | Public board identifier |
|---|---|---|
| Spotify | Lever | `spotify` |
| Vercel | Greenhouse | `vercel` |
| Lovable | Ashby | `lovable` |
| Legora | Ashby | `legora` |
| Temporal | Ashby | `temporal` |

They are enabled on first setup so they can be selected for a job search. Each is initially shown as **Not checked**. Run **Check portal health** from the Portals page to verify actual ATS API availability from your machine; a configured career page URL is not proof that the API is reachable.

## Upgrade and data safety

The starter registry comes from `data/sources.example.json`. The service merges its entries into `data/sources.json` using the ATS provider plus board identifier as the deduplication key.

- Existing user entries are retained.
- Existing entries with the same identifier are not replaced.
- A version 1 marker is upgraded to version 2 and receives any missing starter examples.
- A version 2 marker prevents removed samples from silently reappearing.
- If `data/sources.json` is missing, CareerMate can reconstruct the starter registry even if an old marker file remains.
- Saving the user's configuration marks the starter migration complete.

The human-readable reference is `data/portals.example.json`. The API-compatible configuration template is `data/sources.example.json`. Neither contains credentials.

## Local upgrade

Keep your existing `backend/.env`, `data/sources.json`, candidate profile, job/application records, and workflow history. Replace application source files with the CareerMate 3.3 package, but do not overwrite private local data with example files. On the first Portals API load, the versioned migration adds the five samples once.

## Verification

- Backend test suite includes first-run seed, old-marker migration, duplicate preservation, explicit removal, missing-registry recovery and API GET coverage.
- CSS syntax and TypeScript/TSX syntax are checked as part of release verification.
- The full Vite production build requires installing the frontend dependencies locally with `npm ci`.
