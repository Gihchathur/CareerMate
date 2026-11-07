# CareerMate 0.9 feature expansion

## Job discovery and platform directory
- Curated directory: 58 job platforms, with defaults and user-managed external search shortcuts. The directory distinguishes direct feeds, configurable employer-board adapters and external shortcuts.
- Searchable platform picker. External shortcuts are not represented as automated feeds.
- Direct feeds already present: JobTech/Platsbanken, Remote OK, Arbeitnow, Greenhouse, Lever and Teamtailor.
- New employer ATS adapters: Ashby, Workday, SmartRecruiters, Workable, Recruitee, Breezy HR and Personio.
- Configure employer board identifiers under Settings → Job platforms. Workday requires the full public board URL including tenant, wd cluster and site.
- Public ATS endpoints are accessed with bounded retries and a descriptive User-Agent. Each board fails independently and reports a warning rather than failing the entire search. Successful public ATS board responses are cached locally for 15 minutes.
- Respect provider terms, rate limits and local laws. No LinkedIn/Indeed scraping or account automation is added.

## Job search quality
- Existing cross-source URL/title/company deduplication retained.
- Added conservative salary range extraction from job descriptions.
- Added minimum/maximum salary filters, posting freshness filter and excluded-company filter.
- Unknown salary or publication-date values are not silently treated as matching a user-specified filter.
- Saved searches are stored locally in JSON.
- Daily/weekly saved-search alert schedules run while the local backend process is running (APScheduler dependency required); manual checks remain available.
- New job alerts are stored locally and can be marked read.

## CV tailoring
- `POST /api/cv/tailor` accepts the full job description and one of `classic`, `modern`, `compact`, `sectioned`.
- Requires a saved candidate profile and configured AI provider.
- AI may reorder/rephrase existing evidence but must not add employers, dates, skills, metrics or qualifications.
- Employment identity and chronology fields are checked against the source profile before export.
- Generated DOCX and PDF are stored under `data/cv/tailored/`. Each generation receives a unique version filename; the version-list endpoint and job drawer preserve prior versions.
- `GET /api/cv/tailored/{filename}` downloads DOCX.
- `GET /api/cv/tailored/{filename}/pdf` downloads selectable-text PDF.\n- `GET /api/cv/tailored/{filename}/preview` opens an inline PDF preview.\n- `GET /api/cv/tailored` lists previous generated CV versions.
- The UI exposes the tailored CV action in the job detail drawer, score breakdown, missing keywords, section checks and both download formats.
- Score is a transparent heuristic: keyword overlap (75%) plus section completeness (25%). It is not an ATS-vendor simulation or a guarantee of passing an employer's parser.
- Below 70 is labelled needs improvement. Candidates should add only truthful missing evidence to their base profile and regenerate.

## Configuration and dependencies
- Copy `data/sources.example.json` to `data/sources.json` and configure the employer board slugs you want.
- Install backend dependencies with `pip install -r backend/requirements.txt`; this includes `reportlab` for PDF export and `APScheduler` for recurring local alerts.
- Install frontend dependencies with `npm ci` inside `frontend`, then run `npm run build`.
- Do not commit `backend/.env`, API keys or private candidate data.

## Limitations / next hardening
- Public ATS APIs vary and can change; each connector needs fixture-based contract tests and periodic verification.
- Workday requires the exact tenant/cluster/site URL. It cannot be inferred reliably from a company name alone.
- Salary extraction is best-effort text parsing; salary currencies and pay periods should be reviewed against the source advert.
- Freshness filtering depends on a parseable published date; relative date formats are not yet normalized for every provider.
- PDF is generated from the same structured content as DOCX, not by converting the DOCX renderer; text extraction and a four-page maximum check run automatically, but visually inspect page breaks and Unicode symbols.
- Full end-to-end UI/build verification requires the project's npm dependencies. The supplied archive was missing several model modules imported by the existing backend. These request/record models have now been restored and the complete backend test suite passes in the working copy.
