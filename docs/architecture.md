# CareerMate architecture (current MVP)

```text
React + TypeScript (localhost:5173)
              |
              | local HTTP requests
              v
FastAPI (127.0.0.1:8000)
  |              |                         |
  |              |                         +--> Visible Playwright/Chromium
  |              |                              (reviewed form field preparation)
  |              +--> Job discovery adapters
  |                    |--> JobAd Links / JobTech
  |                    |--> Remote OK / Arbeitnow
  |                    +--> configured Greenhouse / Lever / Teamtailor boards
  |
  +--> Local Ollama model
  |
  +--> Local JSON files
       CV/profile, saved jobs, match cache, applications, source caches
```

## Boundaries

- The browser UI talks to the backend through a configurable local API origin.
- FastAPI's default development command binds to loopback. Do not expose it on a LAN or public interface without adding authentication, request-origin protections, and a deliberate deployment design.
- CV upload is capped at 10 MB; parser output is capped at 60,000 characters and PDFs are capped at 80 pages.
- CV parsing and LLM inference are local. The user-entered job search phrase and location are sent to the public JobAd Links API.
- Matching passes only the professional portion of the saved profile to Ollama; contact fields such as email and phone are excluded.
- Match results are cached in a private JSON file. The cache key includes the job, professional profile, model name and cache version.
- Job advertisement content is untrusted. The model is asked not to follow instructions embedded in source content, and it cannot invoke tools or submit applications.
- Match scores quantify evidence coverage for extracted requirements. They are not hiring probabilities and can be wrong if the local model misreads an advertisement.

## Current limitations

- Job discovery combines the Sweden-focused JobAd Links API, Remote OK remote listings, Arbeitnow job listings, and optionally configured Greenhouse, Lever, and Teamtailor employer boards.
- JobAd Links offers shortened descriptions and links to the provider's full advert; users must open the original listing to verify requirements and application details.
- OCR for image-only CVs is not implemented.
- Browser-assisted form preparation is now implemented for supported public HTTPS pages. It requires visible user review, fills only selected supported fields, and never submits or uploads.
- Semantic retrieval and automatic application submission are not implemented.


## Job source adapters

The discovery service consumes `JobPosting` objects from normalized source adapters. JobAd Links provides the Sweden-focused public free-text source, while Remote OK and Arbeitnow broaden coverage through public feeds and caches. The optional employer adapter registry in `app/services/job_search.py` reads `data/sources.json` and invokes Greenhouse, Lever, and Teamtailor adapters for explicitly configured employer boards. It then applies local role/location/work-mode matching, merges search-role provenance, and deduplicates by listing URL where possible.

The private source configuration is local JSON, not a database. API keys are referenced by environment-variable name only and are never stored in the source JSON or returned by `/api/jobs/sources`. Provider GETs share a short timeout and bounded transient-error retry policy. Enabled board entries and provider response shapes are validated; individual board failures become warnings so one board does not stop successful results from other sources. There is no global ATS crawl or job-application submission.


## Application tracking and draft generation (Step 12)

The Applications view calls the FastAPI application routes. Tracking a job snapshots its title, company, location, public listing URL and description from `data/jobs/jobs.json` into `data/applications/applications.json`. Records are deduplicated by `job_id` and atomically rewritten as JSON. No SQL database or cloud state is added.

Draft-generation endpoints pass the saved profile's professional facts and the application's job snapshot to the configured local Ollama endpoint. Contact fields are omitted. The generated cover letter or question answer is persisted as a draft for manual review. Browser-assisted form preparation is documented below; automatic or unattended submission is not supported.
