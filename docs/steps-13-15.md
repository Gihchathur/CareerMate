# Steps 13–15: acceptance testing, browser assistance, and job-source coverage

## Scope

This milestone combines the planned acceptance-test pass, a user-controlled browser-assisted form-preparation workflow, and broader job-discovery coverage. It keeps CareerMate local-first: FastAPI runs on the same machine, local JSON remains the persistence layer, and Ollama is still the local model integration.

## Step 13 — end-to-end acceptance checks

The backend regression suite covers:

- CV/profile and saved job APIs used by the React UI;
- job source normalization, retries, invalid payloads, partial source failures and cross-source deduplication;
- country/location/work-mode filtering and warnings about approximate totals;
- application persistence, draft generation and duplicate application handling;
- browser-assisted API input validation, safe URL rejection and explicit reviewed-field payloads.

The automated browser workflow is intentionally not an end-to-end test against a live employer website in CI. Live pages, provider APIs, browser installation, and a user's actual Ollama service must be checked on the machine where CareerMate runs.

## Step 14 — browser-assisted form preparation

Install Playwright's Chromium browser once after installing backend requirements:

```powershell
cd C:\CareerMate\backend
.\.venv\Scripts\Activate.ps1
python -m playwright install chromium
```

From an application in the Applications workspace:

1. Choose **Open application page**. CareerMate starts a visible Chromium window and opens the tracked job URL.
2. If the URL is a listing page, navigate to the application form manually, complete any sign-in or verification step yourself, then return to CareerMate and select **Refresh form fields**.
3. Inspect each proposed value. Unchecked fields and blank values are not filled. Edit suggested values before selecting **Fill selected fields**.
4. Review the live form and submit manually on the employer's website. CareerMate exposes no submission endpoint.
5. Close the browser session when finished.

The browser assistant only accepts public HTTPS URLs, rejects internal/private destinations, and blocks browser automation for LinkedIn, Indeed, and Glassdoor. It scans supported visible text fields, email/telephone/URL/date/number inputs and text areas. It deliberately excludes password/OTP/CAPTCHA/security fields, file uploads, checkbox/radio/select controls, submit controls, and hidden/disabled/readonly fields. It does not bypass CAPTCHA, authentication, bot protection, access controls, or rate limits. Browser session data is kept in process memory and is not written to JSON. The manually entered values may remain visible on the employer page until the user closes it.

The scanner is heuristic. Field labels and suggested mappings can be wrong; users must review the label and full value. Location and cover-letter fields should receive extra scrutiny because profile location may not equal a full postal address, and a draft may contain inaccuracies.

## Step 15 — job discovery coverage

### Connected sources

- **JobAd Links (Arbetsförmedlingen ecosystem):** public free-text API, Sweden-focused, updated by the source on its documented schedule. The adapter retains links to the original source job ad.
- **Remote OK:** public remote-jobs JSON feed; no API key is required. Results are cached locally for one hour to reduce repeated feed requests. CareerMate keeps the original listing URL and labels Remote OK as the source. This source only adds remote jobs; it is not a general global in-office/hybrid source.
- **Arbeitnow:** documented public job-board API without an API key. CareerMate limits requests to at most three pages and caches normalized records locally for six hours. Original Arbeitnow listing URLs and source labels are preserved. It is currently used for Germany, the United Kingdom, France, and Switzerland; the feed's available geography and metadata can change.
- **Greenhouse:** employer-specific public job boards. Configure board tokens in `data/sources.json`.
- **Lever:** employer-specific public posting sites. Configure site slugs and region per employer in `data/sources.json`.
- **Teamtailor:** employer-specific API integration. Configure the employer and environment variable name locally; the API key itself must be set in the environment, never committed to JSON.

### Country and work-mode filters

The search UI offers Sweden, Norway, Denmark, Finland, Germany, Netherlands, United Kingdom, United States, Canada, France, Switzerland, and Any country. International results come from Remote OK, Arbeitnow where supported, and configured employer boards; JobAd Links is skipped for a specific non-Swedish country and a warning is shown. Country and city filters are best-effort local filters based on provider metadata and locations. Some feeds omit structured country or work-mode values, so unknown metadata cannot always be filtered perfectly. Selecting a specific work mode excludes unknown mode values.

Arbeitnow's documented API asks clients to link back to Arbeitnow; CareerMate uses the original listing URL and visibly labels the source. Job source counts and totals may be approximate because feeds are paginated differently, remote feeds are filtered locally, and cross-source duplicates are removed. Official references: [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api) and [Arbeitnow API terms](https://www.arbeitnow.com/terms).

## Local verification

Run these commands on the Windows machine hosting the app:

```powershell
cd C:\CareerMate
$env:PYTHONPATH = (Join-Path (Get-Location).Path "backend")
python -m pytest -q

cd C:\CareerMate\frontend
npm ci
npm run build
npm run lint
```

Then start FastAPI and Vite, test an international search using Remote OK, test a configured employer board, track one job, open its official application page, refresh field scanning, fill one test field, and verify that the form was **not submitted** by CareerMate.


## Official documentation and attribution

- [JobAd Links API — Arbetsförmedlingen/JobTech](https://data.jobtechdev.se/dataservice/jobad-links/): public Swedish job-ad search API; no API key or registration is listed as required.
- [Remote OK public feeds and API attribution](https://remoteok.com/faq): explains the public JSON feed and requests credit plus a link to each original listing.
- [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api) and [API terms](https://www.arbeitnow.com/terms): the API terms require a link back to Arbeitnow.
- [Greenhouse Job Board API](https://developers.greenhouse.io/): public job-board endpoints for employer-configured boards.
- [Lever Postings API](https://github.com/lever/postings-api): documented employer-site listing API; public postings are readable, while custom application POSTs require account API access and are not used by CareerMate.
- [Teamtailor API](https://docs.teamtailor.com/): documents public-read permissions, EU, North America, and Asia-Pacific API stacks, pagination, API version headers, and rate limits.
- [Playwright Python locators](https://playwright.dev/python/docs/locators) and [input actions](https://playwright.dev/python/docs/input): official guidance for accessible field discovery and filling controls.

The CI workflow validates backend tests, frontend production build, and ESLint on pushes and pull requests. Live provider connectivity and interactive browser form preparation must still be tested with configured employer boards and a locally installed Chromium browser.
