# CareerMate 3.7.0 — Match insights, portal-only Explore and precise CV attachments

## What changed

### Match Intelligence
- Reworked each job-choice row into two explicit layout regions: job identity/selection and score/status/actions.
- Kept the `View insight` action anchored inside the row at desktop, tablet and mobile breakpoints.
- Applied consistent spacing and wrapping so the action cannot drift to the next row or overlap adjacent cards.

### Branding and navigation
- Added a new gradient CareerMate SVG mark and applied it to the workspace top bar, hover rail and favicon.
- Increased navigation icon dimensions and strengthened the active destination with a violet neon surface, halo and teal edge indicator.
- Preserved the existing compact hover-expanded navigation behavior.

### Employer-portal-only Explore
- Explore source controls now show employer ATS providers only: Greenhouse, Lever, Teamtailor, Ashby, SmartRecruiters, Workable, Recruitee, Breezy HR, Personio and Workday.
- Initial provider selection is derived from enabled boards in `data/sources.json`.
- Search results are filtered against the selected providers and enabled company boards. This also hides old Remote OK, JobTech and other public-feed records from the Explore results view without deleting historical data.
- Saved searches created from Explore require enabled portal providers. Legacy saved searches containing public-feed sources are identified and blocked with a clear migration message instead of quietly reintroducing those feeds into Explore.
- Existing public-feed API connectors remain available for backward compatibility with older integrations; they are not exposed by Explore.

### CV generation and ATS attachments
- The Sectioned Professional template is accepted by the current FastAPI `CvTailorRequest` contract.
- CV Studio can save a target role and company for document naming. Job-specific tailoring automatically passes the selected job title, company and job ID.
- Generated filenames now include candidate, role, company, timestamp and template. Example shape:
  `Gihan_Chathuranga_Backend_Engineer_Spotify_20261107_021500_123456_sectioned.docx`
- The tailored document registry includes the exact PDF filename and role/company/job metadata.
- Documents lists both DOCX and PDF versions with the exact basenames.
- Browser-assisted application review exposes a CV document selector. It can use the original PDF or a tailored PDF. A tailored CV is preselected only when its stored job metadata matches the application; unrelated tailored CVs are never attached silently.
- The backend exports the selected tailored DOCX to PDF if needed and gives Playwright the actual file path, preserving the precise filename in the employer form upload.
- Browser fill responses include `attached_files` with the field ID and exact uploaded basename; the UI confirms the actual attached filename.

## Existing data and compatibility
- No existing jobs, applications, saved searches, candidate profile or portal records are deleted by this release.
- Public-feed job records remain in local storage but do not appear in Explore.
- The existing AI provider settings and local Ollama / OpenAI-compatible configuration are unchanged.
- If the frontend reports that only `classic`, `modern` and `compact` templates are accepted, an older Uvicorn process is still running. Stop it and restart the backend from this CareerMate 3.7.0 package.

## Verification
- Backend test suite: 180 passed.
- Python module compilation: passed.
- TypeScript/TSX syntax transpilation: 16 files passed.
- CSS parsing: 28 stylesheets passed.
- ZIP archive integrity: passed.
- Full Vite production build: not verified in this environment because `npm ci` timed out while reaching the npm registry. The partial `node_modules` directory was removed from the release package.

## Windows setup

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm ci
npm run build
npm run dev
```

When updating an existing installation, preserve `backend/.env` and your `data/` directory. Do not replace `data/sources.json` with the sample file; the sample portal configuration is already included as the initial local configuration in clean installs.
