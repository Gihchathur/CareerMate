# CareerMate 3.8.0

> A redesigned, local-first career operating system for finding opportunities, evaluating fit, preparing applications and tracking outcomes.

<p align="center">
  <img src="frontend/public/careermate-symbol.svg" alt="CareerMate logo" width="88" />
</p>

<p align="center">
  <strong>Local-first, AI-assisted job search and application preparation.</strong><br />
  Search employer career portals, understand CV-to-role evidence, prepare application materials, and review supported form fields before submitting.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/privacy-local--first-2c8a65" alt="Local first" />
  <img src="https://img.shields.io/badge/status-community%20project-596579" alt="Community project" />
</p>

CareerMate 3.8.0 runs on your computer. Candidate profiles, candidate evidence, job records, application drafts and caches are stored in local JSON files. You can use local Ollama inference or configure an online AI API. Hosted AI sends the task content needed for the operation to that provider, and CareerMate requires explicit consent before using a hosted provider.

## CareerMate 3.8.0 workspace

The workflow-first workspace introduces Today, Explore, Inbox, Match intelligence, Scheduled scans, Pipeline, Follow-ups, Portals, Analytics, CV, Documents and Config. Workspace pages share an icon-led heading system and a consistent visual language. The desktop navigation is a full-height left rail that expands to show labels; spacing adapts to shorter laptop viewports so destinations remain visible. Discovered jobs flow into a dedicated triage Inbox before being promoted into the application Pipeline. The existing AI provider configuration, CV studio, candidate evidence vault and local-first storage remain in place. Analytics are calculated from recorded workspace data; historical trends and time-saved metrics are not invented.

## CareerMate 3.8.0 workflow

The workflow foundation adds a dedicated discovery Inbox, triage stages, a Pipeline board, a Today action dashboard, Follow-ups and a Documents library. The Portal directory is seeded with five employer examples (Spotify, Vercel, Lovable, Legora and Temporal) on first launch and during the one-time 3.3/3.4 upgrade. A local workflow event ledger records job discovery, triage and application-stage changes. See [`docs/CAREERMATE_3.0_WORKFLOW.md`](docs/CAREERMATE_3.0_WORKFLOW.md) for the workflow rules, API endpoints, storage paths and remaining roadmap.

The workflow is intentionally human-approved: Explore queries configured employer ATS portals only, and applications are never submitted automatically. External shortcuts, where retained for reference, are not job-ingestion sources. Existing AI provider configuration and local-first data storage are retained.

## Reliable employer-portal discovery

CareerMate 3.8 fetches complete published inventories from selected employer boards where their public ATS endpoints provide them, paginates to the provider-reported end, retains all locally eligible matches in the Inbox, and displays per-company retrieval, title-match, location-match and freshness diagnostics. Explore role matching uses job titles rather than description mentions. Public ATS snapshots are cached for two minutes by default; use **Refresh portals** to bypass that cache and request a live refresh. Provider outages and safety-limit truncation are reported rather than presented as a complete empty result. See [`docs/PORTAL-DISCOVERY-RELIABILITY.md`](docs/PORTAL-DISCOVERY-RELIABILITY.md) for connector behavior and known limits.

## Frontend experience architecture

The interface uses a shared component system and a dedicated CareerMate 3.5 workflow and visual layer:

- `frontend/src/components/layout/WorkspaceShell.tsx` owns the application frame, navigation, page heading, and responsive tab navigation.
- `frontend/src/components/ui/Icon.tsx` provides the shared icon language.
- `frontend/src/components/ui/SourceMark.tsx` provides recognizable source marks for job-board and ATS listings.
- `frontend/src/ux-hardening.css` contains the earlier responsive job-feed and mobile navigation hardening.
- `frontend/src/ux-experience.css` contains the hover-first desktop rail, active-state lighting, ambient canvas treatment, readable page rhythm, drawer hardening and cross-page responsive refinements. `frontend/src/navigation-overflow.css` keeps all desktop destinations visible without a nested sidebar scrollbar and compacts the rail on short screens.
- `frontend/src/styles/tokens.css` defines typography, color, spacing, and motion foundations.
- `frontend/src/styles/layout.css` defines the document-first scrolling layout and responsive navigation.
- `frontend/src/styles/components.css` defines shared forms, buttons, cards, job rows, and dialog surfaces.
- `frontend/src/styles/pages/` contains the existing workflow stylesheets and responsive refinements.
- `frontend/src/careermate-v2.css` provides the new shell, motion, analytics, automation and evidence-vault presentation while the existing workflow logic is progressively migrated into smaller page components.

The document is the page-level vertical scroll container. Navigation does not create a competing page scroll area. On desktop, the full-height left sidebar keeps its expanded labels visible and reserves its width in the workspace grid, so navigation never obscures page content. All destinations remain available without a nested sidebar scrollbar. Phones use a bottom bar and an all-sections sheet. Every workspace destination uses the same icon-led page heading as Explore, while its page body remains tailored to the task. The command palette supports filtered search, arrow-key navigation and Enter to open a destination. Dialogs render through React portals at the document body level; the job and match dialogs use one shared keyboard and scroll-lock lifecycle, including Escape-to-close, focus containment, and focus restoration.

## Features

- Import CV text from PDF, DOCX or TXT and review the extracted candidate profile.
- Search enabled employer ATS portals configured in the Portals directory. Explore does not mix in public aggregators or external shortcuts; historical public-feed records remain stored but are not shown in this view.
- Choose country, city, work arrangement and sources for each search.
- Compare job requirements against profile evidence, with supported, partially supported and not-evidenced classifications.
- Draft tailored cover letters and employer-question answers without intentionally inventing qualifications.
- Track applications, notes, follow-ups and draft materials locally.
- Prepare supported application forms in Chromium, including multi-tab and embedded-frame flows, review values, and explicitly approve final submission.
- Store source-backed professional claims in the local evidence vault; claims remain pending until explicitly verified.
- Review application source health, saved-search preferences and recent alerts in the Automation Centre.
- Review application fields with clear Needs your input, Suggested, Accepted and Filled states before continuing.
- Generate a structured CV layout with a centered headline, categorized technical skills, and clearly divided experience, project, education and achievement sections.
- Review job-match distribution, application funnel and source effectiveness in Career Analytics.
- Use Ollama locally or configure OpenAI and OpenAI-compatible APIs.

AI output is a draft, not a factual guarantee. Review generated claims before using them. Browser support varies by employer site; CareerMate does not bypass sign-in, MFA, CAPTCHA, anti-bot protections, rate limits or access controls. Some sites and custom controls are unsupported.

## Quick start with Docker

Docker Compose is the easiest way to run the web UI and backend together. Use Docker Desktop on Windows/macOS or Docker Engine with the Compose plugin on Linux.

1. Clone the repository and enter its root folder.
2. Create your private provider configuration from the example:

   **PowerShell**
   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

   **macOS/Linux**
   ```bash
   cp backend/.env.example backend/.env
   ```

3. Edit `backend/.env` to choose an AI provider. For Docker, Ollama should be running on the host; the Compose file points the container to `host.docker.internal:11434`. Alternatively, add your hosted provider key to `backend/.env`.
4. Build and start the application:

   ```bash
   docker compose up --build
   ```
5. Open [http://localhost:8080](http://localhost:8080). Stop the application with `Ctrl+C`, or run `docker compose down` in another terminal.

The Compose file binds the UI to `127.0.0.1` by default so it is not published to your LAN. Local workspace data is persisted in `./data`. Back up this directory before upgrading or deleting the project.

**Docker browser limitation:** the Playwright browser runs headlessly inside the container. You can use supported browser preparation steps through CareerMate's review UI, but login, OTP, CAPTCHA and other interactive verification require the native install below. For the full visible Chromium experience, use the native setup.

## Native setup (visible Chromium)

Requirements: Python 3.12 recommended, Node.js 22 LTS, and Chromium installed through Playwright for the backend's active Python environment.

Backend, in PowerShell from the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
uvicorn app.main:app --reload
```

Frontend, in a separate terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The API runs at [http://127.0.0.1:8000](http://127.0.0.1:8000); API docs are at `/docs`.

If Playwright raises `NotImplementedError` on Windows during browser startup, stop Uvicorn and run it without `--reload` as a workaround:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Configure job sources for your country

The **Find jobs** workspace lets you choose the sources used by each search. Built-in sources have different coverage; selecting a source does not mean CareerMate has access to every employer on that platform.

| Source | Coverage and setup |
| --- | --- |
| JobAd Links / Arbetsförmedlingen | Sweden-focused public job feed. |
| Remote OK | Public remote-job feed; availability and location metadata vary. |
| Arbeitnow | Public feed especially useful for selected European markets. |
| Greenhouse | Configure specific public board tokens in `data/sources.json`. |
| Lever | Configure specific company site identifiers and region in `data/sources.json`. |
| Teamtailor | Configure specific company boards and an API key environment-variable name in `data/sources.json`; put the key value in `backend/.env`. |

For a first-time setup, use the richer `data/portals.example.json` template: copy it to `data/sources.json`, then replace the example company names, ATS identifiers and public URLs. If `data/sources.json` already exists, back it up and merge fields rather than overwriting your existing portal list. Keep `enabled` set to `false` until an entry is correctly configured. The active `data/sources.json` is ignored by Git because your board configuration may contain private details. Do not put API key values in that file. See [Portal configuration](docs/PORTAL-CONFIGURATION.md) for provider-specific URL formats and credential handling. See [Sidebar navigation](docs/SIDEBAR-NAVIGATION.md) for navigation behavior and Overview routing.

Country and city filters are best-effort because public feeds often omit structured location data. For country-specific coverage, configure employer boards relevant to that market and check source warnings in the search result. The adapter architecture can be extended for other public APIs, but arbitrary career pages are not automatically supported; a new source requires an adapter, normalization and tests.

Official source docs: [JobAd Links](https://links.api.jobtechdev.se/), [Remote OK](https://remoteok.com/faq), [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api), [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), and [Teamtailor API](https://docs.teamtailor.com/).

## Configure AI

Open **AI provider** in the app to select Ollama, OpenAI API or an OpenAI-compatible provider.

- **Ollama:** install Ollama on the host, pull a model suited to your hardware, and confirm the host URL/model in AI settings. Native default: `http://127.0.0.1:11434`. In Docker Compose, the default host URL is set to `http://host.docker.internal:11434`. If you already saved an Ollama URL in CareerMate's AI settings, update that saved URL there as well, because saved provider preferences take precedence over environment defaults.
- **OpenAI API:** set `OPENAI_API_KEY` in `backend/.env` and select a model ID available to your account.
- **OpenAI-compatible API:** set `CAREERMATE_OPENAI_COMPATIBLE_API_KEY`, `CAREERMATE_OPENAI_COMPATIBLE_BASE_URL`, and a valid `CAREERMATE_OPENAI_COMPATIBLE_MODEL` in `backend/.env`. This supports providers that document OpenAI compatibility; model capabilities and JSON-output support vary.

Never commit `backend/.env`. AI API usage is billed separately from ChatGPT subscriptions. For provider privacy, model names and configuration details, see [AI and data configuration](docs/CONFIGURATION.md). Model IDs and free-tier quotas change, so confirm them in the provider's official docs. [OpenAI models](https://platform.openai.com/docs/models), [Gemini models](https://ai.google.dev/gemini-api/docs/models), [Groq models](https://console.groq.com/docs/models), [Ollama library](https://ollama.com/library).

## Privacy and safety

- Data stays in the local `data/` directory unless you explicitly choose an online AI provider; there is no required account or hosted database.
- API keys belong in environment variables or `backend/.env`, never in source code, JSON preferences, screenshots or commits.
- Browser automation only handles supported public HTTPS pages and is subject to employer-site restrictions.
- Review all proposed answers. Final submission requires a separate explicit approval step; some forms need manual action.
- Never commit your CV, extracted CV text, saved applications, caches, or `data/sources.json`.

See [Privacy and browser boundaries](docs/PRIVACY-AND-SAFETY.md) and the [application automation guide](docs/APPLICATION-AUTOMATION.md).

## Screenshots

Screenshots are intentionally not fabricated. Add sanitized images captured from your running copy under [`docs/screenshots/`](docs/screenshots/README.md), then link them here. Useful screenshots are the overview, job-source selection, match report, AI settings with credentials hidden, and application review screen.

## Development and quality checks

From the repository root, install backend test dependencies:

```bash
python -m pip install -r backend/requirements-dev.txt
python -m compileall -q backend/app
```

Run backend tests with `PYTHONPATH` set (PowerShell):

```powershell
$env:PYTHONPATH = "backend"
python -m pytest -q
```

On macOS/Linux:

```bash
PYTHONPATH=backend python -m pytest -q
```

Frontend checks:

```bash
cd frontend
npm ci
npm run build
npm run lint
```

GitHub Actions runs these backend and frontend checks on pushes and pull requests. Unit tests use mocked providers and do not submit real applications. Before a public release, also run `docker compose config`, build both images, smoke-test `/api/health`, and test native Chromium against an application page you are allowed to access.

See [Development guide](docs/DEVELOPMENT.md) for architecture, test setup and release verification.

## License

MIT. See [LICENSE](LICENSE).


## CareerMate 0.9 feature expansion

The 0.9 work adds a searchable 58-platform directory, additional public employer ATS adapters (Ashby, Workday, SmartRecruiters, Workable, Recruitee, Breezy HR and Personio), local saved searches and scheduled alerts, salary/freshness/company filters, and AI-assisted CV tailoring with four DOCX layouts (including a sectioned professional format with a centered identity header and categorized technical skills), ATS heuristic feedback and PDF export.

See [docs/FEATURE-EXPANSION.md](docs/FEATURE-EXPANSION.md) for setup instructions, capability distinctions and limitations. External job-board shortcuts are not automatic integrations; only configured direct-feed adapters retrieve listings.

## CareerMate 3.8.0 workflow-first navigation and UX

- Desktop has no sidebar toggle button: move the pointer into the 76px SVG icon rail and it expands horizontally; move into the page canvas and it collapses back to icons.
- The expanded width responds to the viewport (238–286px) and the canvas shifts to reserve space rather than being covered.
- Keyboard focus also expands the rail, Escape collapses it, and touch-first phones/tablets use bottom navigation plus an all-sections sheet.
- Active destinations receive a restrained violet halo and teal edge marker. The canvas uses a subtle aurora/drafting-grid treatment without turning every card into a glass panel.
- Cross-page spacing, typography, responsive grids, action wrapping and portalled detail drawers have been hardened.

UX audit and verification notes: [`docs/UX-HARDENING.md`](docs/UX-HARDENING.md). Hover-first preview: [`docs/previews/`](docs/previews/).


## CareerMate 3.7 application automation and CV layout

- Browser-assisted application dropdowns use a searchable, keyboard-operable popover rendered outside page overflow containers.
- Required or question-style fields without answers are highlighted; profile/AI suggestions remain marked for review; manually reviewed values and fields confirmed filled in the employer form have distinct accepted states.
- CV Studio adds a Sectioned Professional layout based on the structure of the saved Backend CV reference: centered name/title, compact two-line contact header, grouped technical skills, dated experience/project/education headings, and clearly divided sections.
- Candidate Profile includes an editable CV headline/title field used below the name in this format.

See [CareerMate 3.7 release notes](docs/CAREERMATE_3.7_RELEASE.md).
