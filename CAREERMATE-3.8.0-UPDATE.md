# CareerMate 3.8.0 update

## What changed

- Explore matches role queries against the vacancy title, not unrelated description or department mentions. For example, `Business Value Consultant` is not a `Software Engineer` match just because its description mentions engineers. `AI Software Engineer` and `Senior Software Engineer` remain valid matches.
- Employer ATS connectors fetch the published/listed inventory exposed by each configured company board, then apply role and location filters locally. Explore stays paginated for usability, but the complete eligible employer-board result set is persisted locally on the first search.
- The Inbox and saved-search alert scans use the complete eligible inventory rather than just the first visible page.
- Teamtailor now requests no more than its documented maximum of 30 jobs per page and follows provider `links.next` cursors or page-count metadata. This fixes a prior truncation bug where a 30-job response to a 100-job request was mistaken for the final page.
- SmartRecruiters and Workday paginate through their reported totals with a 10,000-job per-board safety ceiling. Lever supports up to 20,000 jobs per board (100 per page × 200 pages); Teamtailor supports up to 6,000 (30 per page × 200 pages), following provider next links/page metadata. Any safety-ceiling hit is reported as partial, never as complete.
- Ashby reads `workplaceType` to distinguish OnSite, Remote and Hybrid correctly; `isRemote` alone is not enough because Ashby sets it for both remote and hybrid work. ISO location country values such as `SE` are normalized to `Sweden`.
- Public ATS snapshots have a two-minute default cache. The Explore **Refresh portals** control bypasses the cache and requests a live refresh. When a public ATS refresh fails and a previous snapshot exists, CareerMate retains that snapshot and displays a stale-data warning.
- Every workspace tab uses the same icon-led page-heading structure. Explore additionally reports per-company jobs fetched, title matches, location/work-mode eligible matches, freshness and warnings.

## Legora example

The included starter configuration identifies Legora as an Ashby board with slug `legora`. The public Ashby Job Postings API returns the currently published job postings for that board in its `jobs` array. CareerMate therefore fetches that board inventory first, rather than relying on a keyword-filtered third-party feed. `isListed: false` postings are intentionally excluded because they are not listed on the public job board.

## Reliability boundaries

CareerMate can only retrieve postings exposed by the employer's configured public ATS board and its access permissions. It cannot retrieve drafts, confidential/internal vacancies or jobs omitted by an employer from its public board. An upstream ATS outage, invalid board configuration, rate limit, provider response change or safety limit can still prevent a complete refresh; the per-company coverage panel reports these conditions. Unknown location metadata is treated conservatively, so users should verify the original employer listing before applying. The system does not claim that every public vacancy on the internet is discoverable.

## Validation

- Backend syntax compilation: `python -m compileall -q backend/app backend/tests`.
- Focused portal and matching tests: run `PYTHONPATH=. pytest -q tests/test_portal_discovery_completeness.py tests/test_job_search_regression.py tests/test_portal_health.py`.
- The supplied archive is missing six existing backend model modules imported by `backend/app/main.py` and browser-assistance services: `candidate_evidence.py`, `application.py`, `browser_assistance.py`, `ai.py`, `data_management.py` and `workflow.py` under `backend/app/models/`. Consequently, the full API startup/full test collection cannot be verified from this archive. Restore those existing modules from the complete local repository; do not replace them with placeholders.
- Frontend dependencies were not included in the workspace. Run `npm ci` in `frontend`, then `npm run build` to perform the full frontend production type-check and bundle build.
