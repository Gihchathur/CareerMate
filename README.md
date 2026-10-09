# CareerMate

CareerMate is a local-first, open-source job discovery and CV-matching workspace. It searches a public Swedish job data source, extracts a candidate profile from a CV, and uses a local Ollama model to compare job requirements against evidence in that profile.

## Current capabilities

- Read PDF, DOCX, and TXT CVs locally.
- Extract a structured candidate profile using Ollama.
- Review and edit the profile before matching.
- Search Arbetsförmedlingen's public JobAd Links API for up to five roles per search.
- Optionally include employer-specific Greenhouse, Lever, and Teamtailor boards configured locally.
- Paginate results and apply local work-mode classification where listing metadata or brief text supports it.
- Save normalized job listings in local JSON files.
- Expose `/api/jobs/sources` to report configured source counts without returning credentials.
- Retry temporary provider errors with a bounded backoff, validate listing payloads, and preserve results from healthy employer boards when another board fails.
- Reject incomplete enabled-source configuration early and show warnings instead of silently presenting malformed responses as zero results.
- Compare selected jobs to the profile using a local model and show evidence coverage.
- Cache successful match analyses locally to reduce repeated model calls.
- Use a focused workspace with separate Overview, Find jobs, Match insights, and My profile views.
- Open full job details in a side drawer while keeping search results compact.
- See processing states and transient success/error notifications without losing the current view.
- Track saved roles through application stages with notes, follow-up dates, draft cover letters, and employer-question answers in local JSON.
- Generate reviewable application drafts using the local Ollama model and the reviewed CV profile; generated content is not submitted automatically.

## UI and user experience

The frontend separates job discovery, match reports, and profile maintenance so the CV fields do not appear below the job results in one long page. Overview provides quick status and recent opportunities; Find jobs keeps search filters alongside compact results; selecting a job opens a detail drawer; Applications manages status, notes, follow-up dates and draft materials; My profile contains the editable CV-derived profile. Processing states remain visible in the workspace header, and success/error messages appear as dismissible, auto-closing notifications. The layout adapts to mobile screens. See [`docs/ui-redesign.md`](docs/ui-redesign.md) for UX decisions and the research references used.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+
- Node.js 20.19+ or 22.12+
- Ollama installed locally
- A compatible Ollama model pulled locally (default: `gemma4:e4b`)

## Run the backend

From the repository root, open PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API binds to `127.0.0.1:8000` by default. API documentation: <http://127.0.0.1:8000/docs>.

For a new PowerShell session on Windows, activate the virtual environment again before running the backend.

## Run the frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL Vite prints (normally <http://localhost:5173>).

The frontend can point to another local API URL by setting `VITE_API_URL` in `frontend/.env.local`, for example:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

The backend CORS origins can be configured with `CAREERMATE_CORS_ORIGINS`, as a comma-separated list. Do not bind the API to a public interface without adding an appropriate authentication and security design.

## Configure Ollama

The defaults are:

- `CAREERMATE_OLLAMA_HOST=http://127.0.0.1:11434`
- `CAREERMATE_OLLAMA_MODEL=gemma4:e4b`

Change these using environment variables if needed. For example in PowerShell:

```powershell
$env:CAREERMATE_OLLAMA_MODEL = "gemma4:e4b"
```

Ensure the model is available locally (`ollama list`). Model inference time depends on the model, available memory, and CV/job text length.

## Local data

User data is written under `data/`:

- `data/cv/current.*`: uploaded CV
- `data/cv/extracted_text.txt`: extracted CV text
- `data/cv/profile.json`: structured candidate profile
- `data/jobs/jobs.json`: saved job listings
- `data/jobs/match_cache.json`: successful match results
- `data/applications/applications.json`: application tracking records, notes, cover-letter drafts, and answer drafts

These files are ignored by Git. Only `.gitkeep` files and clearly synthetic `*.example.json` files should be committed. Never commit your actual CV, extracted text, saved profile, application answers, cookies, or browser state.

The UI does not call a cloud LLM. Job search sends the user's search terms to the public job source; it does not upload the CV. The selected job descriptions and a professional-only subset of the candidate profile are passed to Ollama on the configured local host for matching and, when requested, for application draft generation. Draft prompts exclude email, phone, and profile URLs.

## Job data source

CareerMate currently uses the public Arbetsförmedlingen JobAd Links search API. It is a Swedish job-data source; other countries are not connected yet. The API advertises free-text search and filtering, but this implementation sends each job role and city as a free-text query. City is therefore not an exact structured location filter. Work-mode classification is inferred conservatively from available fields and short descriptions; unknown listings remain visible when `Any / not specified` is selected and are excluded when a specific work mode is requested. This may miss listings when descriptions are brief. The total across multiple roles can include duplicate provider hits, so it is labelled approximate. Ads may contain brief descriptions and link to a separate provider's original listing. Always open the original listing to confirm that the job is current and review the complete requirements.

## Optional employer career boards (Step 10)

CareerMate can search the public listings from specific employers that use Greenhouse or Lever, plus Teamtailor accounts for which you have a Public Read API key. These are employer-specific connections; they do **not** create a global search across all companies using these platforms. JobTech remains enabled independently.

1. Copy the template to a private local configuration file from the repository root:

   ```powershell
   Copy-Item data/sources.example.json data/sources.json
   ```

2. In `data/sources.json`, set `enabled` to `true` for a company you want to include and replace the example identifier. Greenhouse uses the job-board token from the employer's Greenhouse career-board URL. Lever uses the site slug from its hosted job-board URL; set `region` to `global` or `eu`. `country` is an optional fallback when a board omits its country in job data.

3. Teamtailor requires a company API key with **Public Read** permissions. Keep the key out of JSON and Git. Set the environment variable named by `api_key_env` in the same PowerShell window before starting the backend, for example:

   ```powershell
   cd backend
   $env:CAREERMATE_TEAMTAILOR_EXAMPLE_API_KEY = "paste-your-local-key-here"
   uvicorn app.main:app --reload
   ```

   Use the environment-variable name you configured in `sources.json`. You need the employer's permission to create/access its Teamtailor API key; do not use a key you are not authorized to use.

4. Restart the backend and refresh the frontend after changing configuration. Check <http://127.0.0.1:8000/api/jobs/sources> to confirm which adapters are configured. Configured and ready sources become selectable in the **Job sources** checkboxes; unconfigured sources remain disabled. This endpoint reports counts, whether a key is required, and whether the configured Teamtailor environment variables are present; it never returns key values.

The adapters fetch public or explicitly authorized read-only job data, normalize it into CareerMate's shared job format, then filter employer-board results locally by title/description, city, country information, and known work mode. Employer boards may expose incomplete location or remote-work metadata, so a result can be missed or its location/work mode can remain unknown. Open the original advert to verify it before applying. The private `data/sources.json` is ignored by Git; only `data/sources.example.json` belongs in the repository.

### Source reliability (Step 11)

Provider GET requests now use a bounded retry policy for transient network failures and HTTP 429/500/502/503/504 responses. Client errors such as 401/403 are not retried. Enabled source configurations are validated before fetching, each board is isolated so a failing employer does not discard successful results from other boards, and response payloads must contain the expected jobs/listing array. Search responses include warnings for sources that fail or have no enabled employer boards. These checks use mocked provider responses in the local test suite; live API availability depends on your network, employer board configuration, and provider service status. See [`docs/job-source-reliability.md`](docs/job-source-reliability.md).

Official documentation: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Teamtailor API](https://docs.teamtailor.com/).


## Application tracker and draft assistant (Step 12)

The **Applications** workspace lets you add a saved job to a local tracker, record the current stage, keep notes, set a follow-up date, edit a cover-letter draft, and store draft answers to employer questions. A job is stored as a snapshot when it is tracked so a later search does not remove its description or change the application record. Adding a job that is already tracked returns the existing record rather than creating a duplicate.

Application stages are `saved`, `preparing`, `applied`, `interview`, `offer`, `rejected`, and `withdrawn`. Updating a record to `applied` records an application timestamp when one has not already been set. The API endpoints are:

- `GET /api/applications` — list records and counts by stage.
- `POST /api/applications` — add a saved `job_id` to the tracker (`{"job_id": "..."}`).
- `PUT /api/applications/{application_id}` — save status, notes, follow-up date, cover-letter text, and answer drafts.
- `POST /api/applications/{application_id}/draft-cover-letter` — generate and save a draft with local Ollama.
- `POST /api/applications/{application_id}/draft-answer` — generate an answer for a question (`{"question": "..."}`).

Drafts use the saved CV profile and the job description snapshot. The prompt excludes the candidate's email, phone, and profile links, instructs the model not to fabricate qualifications or experience, and treats the source text as untrusted. These are safeguards, not a guarantee that model output is perfect: review all generated content and correct any unsupported claim before use. CareerMate does not automatically fill employer forms or submit applications. The final submission must be completed and confirmed by you on the employer's site.

The application store is created automatically as `data/applications/applications.json` on the first tracked job. The committed `data/applications/applications.example.json` is synthetic documentation data only and should not be copied over an actual store unless you intend to add that example record.


## Matching score

The match score is a weighted coverage estimate based on job requirements extracted by the local LLM and evidence found in the reviewed profile. It is not a probability of interview or offer. “Not evidenced” means the profile did not establish the requirement; it does not prove the candidate lacks it. Review the extracted requirements and evidence yourself.

## Tests

Install test dependencies:

```powershell
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
```

From the repository root:

```powershell
$env:PYTHONPATH = "backend"
pytest
```

Frontend checks:

```powershell
cd frontend
npm run build
npm run lint
```

## Project principles

- Local-first storage; no SQL database.
- No bypassing CAPTCHA, MFA, bot detection, access controls, or rate limits.
- No automatic assessments, legal declarations, or unattended application submission.
- AI output is a draft and must be reviewed before use.
