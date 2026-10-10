# Job source reliability (Step 11)

This step improves how CareerMate handles provider downtime and misconfiguration without changing the UI workflow or local-data model.

## Request retry policy

The provider adapters use a shared GET helper:

- At most three attempts per GET request.
- Retries timeouts/transport failures and HTTP `429`, `500`, `502`, `503`, and `504` responses.
- Uses a small exponential delay for transient failures and honors a short numeric `Retry-After` value up to a two-second cap.
- Does not retry other HTTP statuses, including authentication/authorization errors. Retrying a bad key or board token cannot make it valid.
- Does not retry invalid JSON or a wrong payload shape; those failures are reported clearly.

This is intended for an interactive local tool. It is not a bulk crawler and does not intentionally bypass provider limits.

## Configuration validation

Before searching, `data/sources.json` is checked for an object at the root, lists of source entries, object-shaped entries, and required identifiers on enabled entries. Region choices are validated for Lever (`global`, `eu`) and Teamtailor (`eu`, `na`, `apac`). Credentials remain environment-variable values and are never returned in source-status responses.

## Partial failures

Each employer board is isolated. If one board fails after retries, CareerMate reports a warning for that board and retains jobs returned by other working boards. Selecting a source with no enabled configured boards yields a warning instead of an unexplained empty result. The search endpoint still reports an overall error when every selected source fails.

## Response validation

- JobAd Links must return a JSON object containing a `hits` array.
- Greenhouse must return a JSON object containing a `jobs` array.
- Lever must return a JSON array of postings.
- Teamtailor must return a JSON API object containing a `data` array.
- Arbeitnow must return a JSON API object containing a `data` array; its normalized public feed is cached locally for six hours.

A provider response with a missing or wrong-shaped array is not treated as a genuine zero-job result.

## Test coverage and remaining checks

The unit tests mock network responses, so they run offline and verify transient retries, immediate failure for non-transient client errors, payload validation, config validation, and partial results if one employer board fails. The build runner used for this update could not resolve external API hosts, so live source connectivity was not tested. From the user's machine, search a known public Greenhouse board and Lever site, and test Teamtailor only with an API key the user is authorized to use. Do not put the Teamtailor key into `data/sources.json` or source control.

Official provider references:

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html) — public GET endpoints for public jobs do not require authentication.
- [Lever Postings API](https://github.com/lever/postings-api) — supports company-specific posting lists and pagination.
- [Teamtailor API](https://docs.teamtailor.com/) — public job access uses an API key with suitable Public Read permissions.
- [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api) — public no-key API; its listing URLs are retained and the source is labelled in CareerMate.


Remote OK responses are cached in `data/source_cache/remoteok.json` for one hour to reduce repeated calls to its public feed. Arbeitnow uses a separate six-hour cache. Both caches are disposable and excluded from Git.
