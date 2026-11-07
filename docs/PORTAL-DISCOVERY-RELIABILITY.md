# Employer portal discovery reliability

CareerMate Explore is an employer-board discovery pipeline. It retrieves the published inventory from each selected company portal, normalizes the provider records, applies role/location/work-mode filters locally, de-duplicates mirrored URLs, saves all eligible matches, and renders the results in pages.

## Search contract

1. **Portal identity is company-specific.** A job is tagged with a stable `provider:board` ID such as `ashby:legora`. Selecting Legora does not select every Ashby customer.
2. **Fetch before filter.** The ATS connector retrieves the provider's public board inventory first. Search roles are not sent as provider-side text queries because different ATS providers implement search and indexing differently.
3. **Role relevance uses the job title.** The title must contain the requested phrase or all significant role tokens. Job descriptions and department labels are not used as substitutes for the job title. Match Intelligence evaluates skills and experience after discovery.
4. **Location/work-mode filters run after normalization.** Structured city/country fields are preferred. Unknown location metadata is called out; it is not proof that a job is in the selected city.
5. **Persist the full eligible result set.** The API saves every role/location-eligible result from the full selected ATS boards in the local job store on the first search. Explore still displays a page at a time for usability. Scheduled searches compare the full eligible inventory, not only the first page.
6. **Show retrieval coverage.** Explore reports per selected portal: fetched count, title matches, and matches after location/work-mode filtering. Provider failures and pagination safety limits are explicit warnings rather than silent truncation.

## Supported provider retrieval patterns

| Provider | Retrieval pattern | Completeness guard |
|---|---|---|
| Greenhouse | Public board jobs endpoint, full jobs array | Validate response shape; board errors are isolated and reported |
| Lever | `skip`/`limit` pagination, 100 per page | Reads up to 200 pages; safety-limit hit is marked partial |
| Teamtailor | JSON:API pagination, maximum 30 per page | Follows provider `links.next` / page-count metadata; reads up to 200 pages and marks safety-limit hits partial |
| Ashby | Public Job Postings API, `jobs[]` inventory | Includes listed published jobs and structured address, team, department and secondary-location metadata; uses `workplaceType` to distinguish Remote from Hybrid |
| SmartRecruiters | `offset`/`limit`, 100 per page | Continues to `totalFound` or end of feed; 10,000-job safety limit is explicit |
| Workable | Public jobs widget payload | Validates the provider's jobs array |
| Recruitee | Public offers endpoint | Validates the provider's offers array |
| Breezy HR | Public JSON board | Validates the provider's jobs array |
| Personio | Public XML board | Parses all published position elements |
| Workday | CXS `offset`/`limit`, 20 per page | Continues to `total`/`totalCount`/`totalFound` or end of feed; 10,000-job safety limit is explicit |

## Freshness and outage behavior

Public ATS connectors use a short local cache. `CAREERMATE_PORTAL_CACHE_TTL_SECONDS` defaults to 120 seconds. Set it to `0` to disable the cache and request the provider on every search. The Explore **Refresh portals** action bypasses the cache for an explicit live refresh. Cached data is tagged with its last successful fetch timestamp. If an Ashby/SmartRecruiters/Workable/Recruitee/Breezy/Personio/Workday refresh fails and a prior snapshot exists, CareerMate returns the prior snapshot with a visible stale-data warning instead of reporting the company as empty.

Greenhouse, Lever and Teamtailor are requested on each search; transient failures are reported as per-portal errors. Pagination safety limits never silently claim a complete board: when the connector cannot prove it reached the end, the coverage status is `partial` and the warning explains the limit.

## Legora configuration

Legora's public board is configured as an Ashby board with slug `legora` and default country `Sweden`. The expected company-specific portal ID is `ashby:legora`. Verify that your local `data/sources.json` still has that enabled entry; the example registry is only a template and does not replace an existing local registry.

## Important limits

“Complete” means all currently published/listed jobs that the configured public provider endpoint exposes when the request succeeds. No connector can retrieve draft, unlisted, expired, private, login-only, or provider-hidden postings. ATS APIs may rate-limit, change response formats, or return incomplete metadata. A board configured with the wrong slug/site/token will not yield the employer's jobs. CareerMate therefore keeps the original employer job URL for final verification and exposes source coverage/freshness rather than claiming that every vacancy on the public internet is guaranteed to be found.

This is an API-first approach, not an HTML scraper. If a company uses a proprietary career site or a board with no supported public endpoint, it needs a dedicated connector; the career-page URL by itself is not enough to infer a reliable feed.
