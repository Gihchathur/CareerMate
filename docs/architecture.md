# CareerMate architecture (current MVP)

```text
React + TypeScript (localhost:5173)
              |
              | local HTTP requests
              v
FastAPI (127.0.0.1:8000)
  |          |              |
  |          |              +--> JobAd Links API (search terms only)
  |          |                          |
  |          +--> local Ollama <---------+ (job descriptions returned by source)
  |                      |
  +--> local files ------+
       data/cv/profile.json
       data/cv/extracted_text.txt
       data/jobs/jobs.json
       data/jobs/match_cache.json
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

- Job discovery currently uses one Sweden-focused public source.
- JobAd Links offers shortened descriptions and links to the provider's full advert; users must open the original listing to verify requirements and application details.
- OCR for image-only CVs is not implemented.
- Semantic retrieval, application form assistance, application tracking and application submission are future features, not current capabilities.
