# Employer portal configuration

CareerMate keeps employer ATS configuration in the local data folder. The active file is:

```text
data/sources.json
```

It is intentionally git-ignored because it represents your personal company watchlist. A reusable, non-secret template is included at:

```text
data/portals.example.json
```

## Set up the registry

1. For a brand-new setup only, copy `data/portals.example.json` to `data/sources.json`. **If `data/sources.json` already exists, do not overwrite it**: back it up, then add the optional URL and notes fields to your existing entries or edit them in CareerMate → Portals.
2. Open `data/sources.json` in VS Code or another JSON editor.
3. Replace the example company names, ATS identifiers and URLs with the company's actual public details.
4. Keep `enabled` set to `false` until the identifiers and URLs have been checked.
5. Alternatively, add or edit the same company details directly in CareerMate → Portals.
6. Save the configuration, enable the portal and run **Check portal health**.

The file uses the same provider-key structure as the backend API, so it can be copied directly to `data/sources.json`. The `_document` object is descriptive metadata; CareerMate's source-config validator ignores it and reads the supported provider arrays.

## Supported provider identifiers

| Provider | Identifier field | Public jobs URL pattern |
|---|---|---|
| Greenhouse | `board_token` | `https://boards.greenhouse.io/{board_token}` |
| Lever | `site` | `https://jobs.lever.co/{site}` |
| Teamtailor | `company` plus `api_key_env` | Use `jobs_url` for the public career page; API reads require an API key |
| Ashby | `slug` | `https://jobs.ashbyhq.com/{slug}` |
| SmartRecruiters | `slug` | `https://jobs.smartrecruiters.com/{slug}` |
| Workable | `slug` | `https://apply.workable.com/{slug}` |
| Recruitee | `slug` | `https://{slug}.recruitee.com` |
| Breezy HR | `slug` | `https://{slug}.breezy.hr` |
| Personio | `slug` | `https://{slug}.jobs.personio.de` |
| Workday | `slug` | Full `https://{tenant}.wdN.myworkdayjobs.com/{site}` URL |

## URL fields

Each employer entry may include:

- `career_url`: the company's general career page, which is useful for people and manual review.
- `jobs_url`: the public ATS job-board URL. This is a clickable reference in the Portals directory. CareerMate still uses the provider-specific identifier to call supported public APIs.
- `notes`: optional setup notes for the portal.

Both URL fields must be public HTTPS URLs. They are links for navigation and record-keeping; storing a URL does not make an unsupported portal automatically searchable.

## Credentials and privacy

Never put credentials, API keys, cookies, session tokens or passwords in `sources.json` or `portals.example.json`. For Teamtailor, set the value of the configured environment variable in `backend/.env`; the JSON stores only the variable name, for example `CAREERMATE_TEAMTAILOR_EXAMPLE_API_KEY`.

`data/sources.json` is excluded from Git. Keep it in your local data backup if you want to preserve your portal directory across installations. The `.example.json` template is safe to commit because all entries are disabled and use placeholder identifiers.

## Where the configuration is stored

The active registry is a JSON document at `data/sources.json`. The UI reads and writes this same file through the local API. The sample `data/portals.example.json` is intentionally safe to commit: all entries are disabled and identifiers are placeholders. Keep your own `data/sources.json` in a local backup when upgrading CareerMate.
