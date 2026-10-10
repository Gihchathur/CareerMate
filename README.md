# CareerMate

CareerMate is a local-first, open-source job discovery and application workspace. It searches public job feeds and configured employer boards, extracts a candidate profile from a CV, and compares job requirements against evidence in that profile using a selectable AI provider: local Ollama, OpenAI API, or an OpenAI-compatible API.

## Current capabilities

- Read PDF, DOCX, and TXT CVs locally.
- Extract a structured candidate profile using the selected AI provider (Ollama, OpenAI API, or an OpenAI-compatible API).
- Review and edit the profile before matching.
- Search Arbetsförmedlingen's public JobAd Links API for up to five roles per search.
- Search public Remote OK remote listings and Arbeitnow's documented job-board API, while preserving provider attribution and listing URLs. Remote OK results are cached for one hour and Arbeitnow results for six hours in disposable local JSON cache files.
- Optionally include employer-specific Greenhouse, Lever, and Teamtailor boards configured locally.
- Paginate results and apply local work-mode classification where listing metadata or brief text supports it.
- Save normalized job listings in local JSON files.
- Expose `/api/jobs/sources` to report configured source counts without returning credentials.
- Retry temporary provider errors with a bounded backoff, validate listing payloads, and preserve results from healthy employer boards when another board fails.
- Reject incomplete enabled-source configuration early and show warnings instead of silently presenting malformed responses as zero results.
- Compare selected jobs to the profile using the selected AI provider and show evidence coverage. Cloud-provider matches can run concurrently (up to four at a time); Ollama remains sequential to reduce local CPU/RAM pressure.
- Cache successful match analyses locally by job, profile, provider, and model to reduce repeated model calls.
- Use a focused workspace with separate Overview, Find jobs, Match insights, and My profile views.
- Open full job details in a side drawer while keeping search results compact.
- See processing states and transient success/error notifications without losing the current view.
- Track saved roles through application stages with notes, follow-up dates, draft cover letters, and employer-question answers in local JSON.
- Generate reviewable application drafts using the selected AI provider and the reviewed CV profile; generated content is not submitted automatically.

## UI and user experience

The frontend separates job discovery, match reports, and profile maintenance so the CV fields do not appear below the job results in one long page. Overview provides quick status and recent opportunities; Find jobs keeps search filters alongside compact results; selecting a job opens a detail drawer; Applications manages status, notes, follow-up dates and draft materials; My profile contains the editable CV-derived profile. Processing states remain visible in the workspace header, and success/error messages appear as dismissible, auto-closing notifications. The layout adapts to mobile screens. See [`docs/ui-redesign.md`](docs/ui-redesign.md) for UX decisions and the research references used.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+
- Node.js 20.19+ or 22.12+
- Ollama installed locally with a compatible model (default: `gemma4:e4b`) if you want local inference; this is optional when using a hosted provider
- An API key and API billing configured with your chosen provider if you want hosted inference

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
- `data/source_cache/arbeitnow.json`: six-hour cached public job feed (not personal data)

These files are ignored by Git. Only `.gitkeep` files and clearly synthetic `*.example.json` files should be committed. Never commit your actual CV, extracted text, saved profile, application answers, cookies, or browser state.

Job search sends the user's search terms to the selected public job source; it does not upload the CV. AI processing uses the provider selected under **AI provider**. With Ollama, inference runs on the configured local host. With a hosted provider, task-specific text is sent to that external service. Job matching uses professional profile facts without direct contact details; application-draft prompts exclude email, phone, and profile URLs.

## Job discovery sources (Steps 10, 11 and 15)

CareerMate combines the public Arbetsförmedlingen JobAd Links feed for Sweden, Remote OK's public remote-jobs feed, Arbeitnow's public job-board API, and locally configured employer-specific Greenhouse, Lever and Teamtailor boards. Remote OK and Arbeitnow require no API key; CareerMate preserves source labels and original listing links. Remote OK focuses on remote jobs and is not a global source for every on-site or hybrid role. Arbeitnow is a Europe-oriented aggregator and is currently used for Germany, the United Kingdom, France and Switzerland. Its public API is cached locally for six hours to avoid needless repeated requests.

The search UI supports Sweden, Norway, Denmark, Finland, Germany, Netherlands, United Kingdom, United States, Canada, France, Switzerland, and Any country. International availability depends on Remote OK's remote listings, Arbeitnow where supported, and the specific employer boards configured in `data/sources.json`; this is not a universal search across every job website. JobAd Links is Sweden-focused. City, country, and work-mode filters are best-effort local filters because providers do not consistently publish structured location metadata. Unknown work modes are excluded when a specific work mode is selected. Job totals can be approximate due to local filtering, provider pagination, and deduplication. Always open the original job listing to confirm that it is current and review the full requirements.

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

Official documentation: [JobAd Links API](https://links.api.jobtechdev.se/), [Remote OK public feeds](https://remoteok.com/faq), [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api) and [terms](https://www.arbeitnow.com/terms), [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Teamtailor API](https://docs.teamtailor.com/).


## Application tracker and draft assistant (Step 12)

The **Applications** workspace lets you add a saved job to a local tracker, record the current stage, keep notes, set a follow-up date, edit a cover-letter draft, and store draft answers to employer questions. AI-generated materials use the currently selected provider. A job is stored as a snapshot when it is tracked so a later search does not remove its description or change the application record. Adding a job that is already tracked returns the existing record rather than creating a duplicate.

Application stages are `saved`, `preparing`, `applied`, `interview`, `offer`, `rejected`, and `withdrawn`. Updating a record to `applied` records an application timestamp when one has not already been set. The API endpoints are:

- `GET /api/applications` — list records and counts by stage.
- `POST /api/applications` — add a saved `job_id` to the tracker (`{"job_id": "..."}`).
- `PUT /api/applications/{application_id}` — save status, notes, follow-up date, cover-letter text, and answer drafts.
- `POST /api/applications/{application_id}/draft-cover-letter` — generate and save a draft with the selected AI provider.
- `POST /api/applications/{application_id}/draft-answer` — generate an answer for a question (`{"question": "..."}`).

Drafts use the saved CV profile and the job description snapshot. The prompt excludes the candidate's email, phone, and profile links, instructs the model not to fabricate qualifications or experience, and treats the source text as untrusted. These are safeguards, not a guarantee that model output is perfect: review all generated content and correct any unsupported claim before use. CareerMate does not automatically fill employer forms or submit applications. The final submission must be completed and confirmed by you on the employer's site.

The application store is created automatically as `data/applications/applications.json` on the first tracked job. The committed `data/applications/applications.example.json` is synthetic documentation data only and should not be copied over an actual store unless you intend to add that example record.

### Browser-assisted application preparation (Steps 13–14)

From an application record, CareerMate can open a visible local Chromium browser at the job URL, scan supported visible fields, suggest values from your reviewed profile and drafts, and fill only the fields you explicitly select. It never clicks Submit, uploads files, fills password/OTP/CAPTCHA/security fields, or attempts to bypass sign-in, MFA, bot detection, access controls, or rate limits. Browser automation is blocked on LinkedIn, Indeed, and Glassdoor. You must navigate to the application form yourself where necessary, review the proposed values, and submit manually on the employer's site.

Install the browser binary once after installing backend dependencies:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m playwright install chromium
```

Browser form values and browser cookies are not written to CareerMate's JSON stores. The browser session exists only while the backend process is running; close the browser session after you're done. See [`docs/steps-13-15.md`](docs/steps-13-15.md) for the complete workflow and local verification checklist.


## AI provider settings

Open **AI provider** in the workspace navigation to choose between local Ollama, the OpenAI API, and a generic OpenAI-compatible endpoint. API keys belong in the private `backend/.env` file; they are never saved in JSON preferences or returned by the settings API. For hosted providers, the UI requires explicit acknowledgement that task content (CV text, profile facts, and job/application details as needed) may be sent to the provider. Test connection sends only a generic ping. Open `docs/ai-providers.md` for setup, supported configuration, privacy notes, performance behavior, and official references.

**Billing note:** ChatGPT subscriptions and OpenAI API usage have separate billing. A paid ChatGPT subscription does not automatically cover this application's API usage. See the [official billing explanation](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform).

## Matching score

The match score is a weighted coverage estimate based on job requirements extracted by the selected AI provider and evidence found in the reviewed profile. It is not a probability of interview or offer. “Not evidenced” means the profile did not establish the requirement; it does not prove the candidate lacks it. Review the extracted requirements and evidence yourself.

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


## Continuous integration

GitHub Actions runs the backend tests and Python compilation, then installs frontend dependencies and runs the Vite production build and ESLint. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml). The automated suite uses mocked provider responses and does not bypass authentication or interact with live employer forms.

For the complete acceptance procedure, browser assistance safety boundaries, source limitations, and official API references, see [`docs/steps-13-15.md`](docs/steps-13-15.md).
