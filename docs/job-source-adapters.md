# Job source adapters (Step 10)

CareerMate has one generic search provider plus optional employer-specific adapters.

| Adapter | Required setting | API access | Scope |
|---|---|---|---|
| JobAd Links | Built in | Public search endpoint | Swedish job search |
| Greenhouse | `board_token` | Public GET Job Board API | One employer board per entry |
| Lever | `site`, `region` | Public postings API | One employer site per entry |
| Teamtailor | `company`, `api_key_env`, `region` | Authorized API key with Public Read | One employer account per entry |

## Configure

Copy `data/sources.example.json` to `data/sources.json`, configure company identifiers, and set `enabled` to `true` for the boards to include. The private `data/sources.json` file is ignored by Git. Teamtailor keys must be supplied through the configured environment variable, not committed or placed in JSON.

All adapters return the shared `JobPosting` model. Listings are matched locally against job title/description and available location/work-mode fields. This is intentionally conservative and does not guarantee complete matching where providers omit data. Pagination for employer-board results is local to CareerMate because board APIs do not provide a global cross-company search.

The UI uses `GET /api/jobs/sources` to enable only configured and ready adapters. The endpoint returns safe configuration metadata only. Users can select which enabled providers to query for each search.


## Reliability and troubleshooting

Transient HTTP/network failures use a bounded retry policy. Bad credentials and invalid board identifiers are not retried, and malformed provider responses are surfaced as warnings/errors rather than empty results. See [`job-source-reliability.md`](job-source-reliability.md) for the retry policy and test coverage.
