# Job search preferences and pagination

CareerMate's first discovery adapter uses the public Arbetsförmedlingen JobAd Links API. Search preferences are implemented conservatively:

- Up to five job titles/queries can be entered, one per line.
- Each role is queried separately; city is appended to each free-text query when provided.
- Sweden is the only configured country at this point. Other UI options are disabled until a compatible source is implemented.
- Results can be paginated with a page size of 10, 20, or 40.
- Result pages from each role are interleaved and deduplicated before being shown.
- Work mode is `remote`, `hybrid`, `on_site`, or `unknown` based on explicit structured metadata or clear phrases in the available short listing text.
- Selecting a specific work mode excludes `unknown` results. Choose `Any / not specified` to avoid this exclusion.
- Work mode is inferred locally, not represented as a guaranteed native API filter. City is sent as part of the free-text query, not an exact structured location filter.
- Provider totals summed across multiple queries may include duplicates. The UI explains that the count is approximate in those cases.
- Search results and the roles which surfaced them are kept in local JSON.

## API

`GET /api/jobs/search` accepts repeated `roles` query parameters plus `country`, `city`, `work_mode`, `limit`, and `offset`. The older `query` and `location` parameters remain supported for a single-role client.

Examples:

```text
/api/jobs/search?roles=Platform%20Engineer&roles=DevOps%20Engineer&country=Sweden&city=Stockholm&work_mode=any&limit=20&offset=0
/api/jobs/search?roles=Accountant&country=Sweden&city=Gothenburg&work_mode=hybrid&limit=10&offset=10
```

The second example is a demonstration of request shape; a result is returned only when the source has enough entries whose available text indicates hybrid work.
