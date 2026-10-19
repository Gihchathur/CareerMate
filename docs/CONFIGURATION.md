# Configuration guide

This guide documents provider and job-source setup. Do not commit real API keys, candidate profiles, CVs or private board configuration.

## AI providers

### Ollama (local)

1. Install Ollama on the host OS and pull a model supported by your memory/compute budget.
2. Keep `CAREERMATE_AI_PROVIDER=ollama` in `backend/.env` if you want local inference as the default.
3. Native default URL is `http://127.0.0.1:11434`. In Docker Compose, the host is `http://host.docker.internal:11434`.
4. Select an installed model in CareerMate's AI settings and use Test connection.

### OpenAI API

Set `OPENAI_API_KEY` in `backend/.env`. Select a model ID available for your account in the AI settings. API usage is billed separately from ChatGPT subscriptions. Reference: <https://platform.openai.com/docs/models>.

### OpenAI-compatible providers

Set the following in `backend/.env`:

```dotenv
CAREERMATE_OPENAI_COMPATIBLE_API_KEY=
CAREERMATE_OPENAI_COMPATIBLE_BASE_URL=
CAREERMATE_OPENAI_COMPATIBLE_MODEL=
```

Use the exact URL/model required by the provider's official docs. CareerMate uses the provider's OpenAI-compatible API contract; that does not guarantee compatibility with every advanced feature or strict JSON schema. Reference: <https://platform.openai.com/docs/api-reference/chat>.

Hosted providers may receive CV text, profile facts, advert text, or draft text needed for the requested AI operation. CareerMate requires an explicit consent action in AI settings before sending personal/job content to a hosted model. Inspect provider retention/training terms before use.

## Employer job boards

The UI's source checkboxes select which sources a search should use. Public feed availability is managed by the source adapter. Employer-board integrations are opt-in per board in a local file.

1. Copy `data/sources.example.json` to `data/sources.json`.
2. Set `enabled: true` only for a real board that you have configured.
3. Add each board to its source array. Entries can include `company` and `country` to improve listing labels.
4. Keep secret values out of JSON. Teamtailor entries refer to an environment variable by name; set that variable in `backend/.env`.
5. Restart the backend and check the source status in the Find jobs UI.

Example shapes:

```json
{
  "greenhouse": [
    { "enabled": true, "board_token": "public-board-token", "company": "Example", "country": "United States" }
  ],
  "lever": [
    { "enabled": true, "site": "public-company-site", "company": "Example", "region": "global", "country": "Canada" }
  ],
  "teamtailor": [
    { "enabled": true, "company": "Example", "api_key_env": "CAREERMATE_TEAMTAILOR_EXAMPLE_API_KEY", "region": "eu", "country": "Germany" }
  ]
}
```

These identifiers are illustrative placeholders; do not enable them without the actual employer board values. Supported Teamtailor regions are `eu`, `na`, and `apac`; Lever supports `global` and `eu`. The adapter uses public job listing endpoints or user-configured read access where applicable.

Country selection is not tied to a single national source. The source list is the actual coverage boundary: JobAd Links is Sweden-focused, Remote OK is remote-focused, Arbeitnow covers the markets described in its feed, and employer ATS adapters work only for configured boards. Adding a new provider/platform requires a new adapter plus unit tests; CareerMate does not crawl all employers automatically.

Official docs: [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [Teamtailor API](https://docs.teamtailor.com/), [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api), [Remote OK FAQ](https://remoteok.com/faq), [JobAd Links API](https://links.api.jobtechdev.se/).
