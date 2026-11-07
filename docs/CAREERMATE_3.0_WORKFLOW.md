# CareerMate 3.0 — workflow foundation

This release begins the Career Ops-inspired workflow redesign while retaining CareerMate's existing FastAPI backend, React/Vite frontend, local-first JSON stores and AI provider configuration.

## Primary navigation

- **Today** — daily action queue, key counts and recent workflow activity.
- **Explore** — existing multi-source job search. Searches continue to use supported integrated sources. Selected external shortcuts open in their own browser tabs and are not scraped.
- **Inbox** — discovered jobs not yet represented by an application record. Jobs can be reviewed, shortlisted, skipped or promoted to the Pipeline.
- **Match intelligence** — existing evidence-based matching workspace.
- **Scheduled scans** — existing saved-search and alert experience. A full schedule execution history/worker-health manager remains a later milestone.
- **Pipeline** — Kanban lanes for preparation, applied, interview, offer and closed records. Selecting a card opens the existing application detail and AI drafting editor.
- **Follow-ups** — view dated and undated next actions from active application records. Automatic email sending and configurable cadence rules are not enabled.
- **Portals** — existing employer ATS/source configuration.
- **Analytics** — existing analytics views.
- **CV** — existing candidate profile and CV studio.
- **Documents** — local tailored-CV and cover-letter collection.
- **Config** — existing AI, privacy and data configuration.

## Workflow state storage

CareerMate does not migrate or rewrite existing job and application records for this milestone.

- `data/jobs/jobs.json` remains the canonical discovered-job store.
- Existing application JSON remains the canonical application store.
- `data/workflow/job_triage.json` stores only triage metadata keyed by job ID.
- `data/workflow/events.json` stores a bounded, newest-first activity history (maximum 1,000 events).

The workflow files are created on first write. Writes use a temporary file and atomic replacement. Activity telemetry is best-effort and does not block core job/application operations.

## API endpoints

- `GET /api/workflow/inbox` — untracked discovered jobs, triage records and per-stage counts.
- `PUT /api/workflow/jobs/{job_id}/triage` — set `new`, `reviewing`, `shortlisted` or `skipped`.
- `GET /api/workflow/activity?limit=30` — bounded recent activity history.

## Important flow rules

1. A completed integrated job search saves jobs using the existing discovery storage and then refreshes the Inbox.
2. Jobs already linked to an application record are excluded from the Inbox.
3. Promoting a job creates or opens its existing application record; it is therefore removed from the Inbox on refresh.
4. Pipeline stage changes update the existing application record and add an activity event.
5. External search shortcuts (LinkedIn, Indeed, Glassdoor) open user-controlled search pages. CareerMate does not scrape those pages.
6. CareerMate never clicks a final employer submission button on the user's behalf in this workflow.

## Next milestones

- Full saved-scan scheduler controls, execution history and source health.
- Dedicated employer Portal watchlist, last-scan state, retry and failure diagnosis.
- Follow-up cadence rules, recruiter/contact history and response classification.
- Evidence-linked match evaluation and document/answer claim verification.
- Richer Pipeline filters, saved views, list mode and bulk triage.
- Historical analytics based on workflow events, not only current state snapshots.
- Company research, interview prep, STAR story bank and outcome learning.
