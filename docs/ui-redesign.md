# CareerMate UI redesign

## What changed

The frontend now uses a workspace navigation model rather than placing every workflow in one long document:

- **Overview** gives a quick snapshot of collected opportunities, profile readiness, and match analysis, plus links into the next useful action.
- **Find jobs** keeps search criteria beside a filterable result list. Job summaries are compact; the full available description and source link open in a right-side detail drawer.
- **Match insights** separates evidence-based match reports from raw job discovery.
- **My profile** isolates CV upload/analysis and the reviewed profile editor. Experience and education entries are collapsed by default to reduce page length.

The design also introduces a responsive desktop sidebar/mobile navigation, clearer visual hierarchy, status indicators, processing states, auto-dismissing success/error toasts, a keyboard-dismissible job drawer, clearer empty states, and a profile completeness indicator. It preserves the existing API calls and local JSON storage; no account, hosted service, database, or new backend dependency is introduced.

## UX research used

The interaction model was informed by public help documentation from existing job-search products:

- **Simplify** organizes job search around a tracker, filters, and stages; its docs describe filtering by company, role, date, type, or stage and switching between different list/column views. CareerMate borrows the general ideas of focused views and clear status/filter controls without adding a fake application pipeline that the current backend does not support. See [Using the Job Tracker](https://help.simplify.jobs/help/articles/2140179-using-the-job-tracker).
- **Huntr** presents job tracking as a central command surface with separate areas for job cards, activities, metrics, contacts, and documents. CareerMate uses a similar separation of concerns at a smaller scope: discovery, matching, profile, and overview. See [Job Tracker](https://help.huntr.co/en/articles/9883324-job-tracker).
- **Teal** documents sorting and grouping in its job-tracker grid. CareerMate currently offers searchable compact results and a detail drawer; the present backend does not yet support a real application-status board, so the redesign does not invent one. See [Exploring the Dashboard](https://help.tealhq.com/en/articles/9524944-exploring-the-dashboard).

This is an original local-first layout, not a copy of any product's branding or screen designs.

## Local verification

After restoring/installing project dependencies, run:

```powershell
cd frontend
npm ci
npm run build
npm run lint
```

Backend tests:

```powershell
cd ..
$env:PYTHONPATH = (Join-Path (Get-Location).Path "backend")
python -m pytest -q
```

`App.tsx` and `main.tsx` passed TypeScript syntax transpilation and a targeted TypeScript check against temporary framework type stubs in this inspection environment. The full Vite build and ESLint command could not be run here because frontend packages could not be fetched in the isolated environment. Backend tests passed in the inspection environment with a temporary Ollama import stub; this verifies the unit tests but does not exercise live model inference.
