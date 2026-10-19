# Development and release guide

## Architecture

- `frontend/`: React, TypeScript and Vite single-page application.
- `backend/app/`: FastAPI API, Pydantic request/response models, AI services, CV parsing, job source adapters, matching, application tracking and Playwright automation.
- `data/`: local runtime JSON and uploaded CV files. Only `.example.json` templates and `.gitkeep` files belong in Git.
- `tests/` and `backend/tests/`: backend regression tests. CI runs them without live AI calls or real employer submissions.
- `Dockerfile.backend`, `frontend/Dockerfile`, `compose.yaml`: containerized UI/API development setup.

## Local checks

From the repository root:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m compileall -q backend/app
```

PowerShell:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

macOS/Linux:

```bash
PYTHONPATH=backend python -m pytest -q
```

Frontend:

```bash
cd frontend
npm ci
npm run build
npm run lint
```

The browser requires a Playwright Chromium binary for native mode:

```bash
python -m playwright install chromium
```

Run tests before changing matching, application persistence or browser automation. AI model responses and source feeds must be mocked in unit tests unless a separate opt-in integration test is clearly labelled.

## Docker

```bash
# Create backend/.env from the example before the first start.
docker compose config
docker compose up --build
```

The UI is published to `http://localhost:8080`, backend health is checked internally, and `./data` is mounted for persistence. The container runs Chromium headlessly. Native mode is recommended for browser flows that require a visible browser, interactive sign-in or manual security checks. The default Compose port binding is loopback-only; don't expose this personal-data application to a public network without adding authentication and a proper threat model.

## Job source additions

Implement a source adapter under `backend/app/services/job_sources/`, normalize results into `JobPosting`, guard response size/timeouts and malformed responses, preserve source attribution, and add mocked tests for normal, empty, malformed, rate-limited and unavailable responses. Add the source ID to discovery validation and the frontend source option/type. Document geographic/API limitations. Do not scrape private endpoints or circumvent access controls.

## Release checklist

- [ ] `backend/.env` is private and absent from the release archive.
- [ ] `data/` contains no real CV, profile, saved applications, cached listings or AI preferences.
- [ ] Backend tests pass with no developer-local settings influencing them.
- [ ] Frontend production build and lint pass.
- [ ] `docker compose config` parses and both images build.
- [ ] Smoke test `http://localhost:8080` and backend `/api/health`.
- [ ] Test one supported public source, one configured employer board and the empty/failure states.
- [ ] Test application preparation on a public page without submitting an application.
- [ ] Capture sanitized screenshots; hide credentials, private CV details and employer account information.
- [ ] Manually review README commands and supported/unsupported behavior.

A green test suite does not guarantee every employer ATS works. Label live provider/browser checks separately from mocked automated tests.
