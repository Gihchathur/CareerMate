# CareerMate 3.5 — Inbox freshness and navigation polish

## Navigation

- The navigation rail remains narrow and hover-expanded; no collapse button or nested scroll area was introduced.
- Primary line icons are now 18px, with 16px and 15px responsive reductions on short and extremely short screens.
- Section separators have slightly stronger contrast and expanded-mode section labels are easier to scan. The compact state remains icon-only.

## Why cleared jobs could remain visible

The Inbox is derived from `data/jobs/jobs.json` and is loaded into React state as `workflowInboxData`. Deleting the local files does not automatically invalidate that in-memory state. The previous navigation action also changed the active page without reloading the Inbox, so an already-open session could continue showing the pre-reset count.

## Fixes

1. A successful full workspace reset immediately clears `workflowInboxData` and `workflowEvents` in the frontend.
2. A reset invalidates any outstanding workflow fetch using a monotonically increasing request generation. A slow response started before the reset cannot overwrite the cleared state.
3. Returning to Inbox or Today performs a fresh workflow read.
4. Workflow Inbox and activity reads use `cache: "no-store"` in the browser; FastAPI sends `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` and `Pragma: no-cache`.
5. The reset handler verifies that the server reports zero saved jobs and zero applications. If not, it reports a backend/workspace mismatch rather than claiming the reset succeeded.

## Clear cache vs. reset workspace

- **Clear caches** removes derived source/match caches but intentionally keeps saved job records. Those jobs can continue to appear in the Inbox.
- **Reset all local data** deletes user-generated data under `data/`, including `jobs/jobs.json` and workflow triage/activity state. API keys in `backend/.env`, source code, and the Python environment are preserved.

## Regression coverage

`tests/test_workflow_api.py::test_workspace_reset_clears_saved_jobs_and_the_workflow_inbox` verifies the reset API, zero-count summary, empty Inbox, empty triage counters, empty event history, and `Cache-Control: no-store` behavior.

## Clear cache versus empty Inbox

The Data & Privacy screen now explicitly states that **Clear caches** does not empty the Job Inbox. It only removes derived source/match caches; saved job records remain. To remove Inbox jobs, use **Clean everything** and complete the confirmation phrase. The full reset clears saved jobs and workflow triage/activity records, then refreshes the current UI state from the backend.
