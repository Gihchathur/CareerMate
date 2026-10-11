# CareerMate AI performance analysis and roadmap

**Reviewed:** 11 October 2026  
**Scope:** Repository snapshot supplied for this review. No live provider calls or benchmarks against the developer's Windows machine were available.

## Findings in the current code

### Job matching

`backend/app/services/job_matcher.py` sends the job description (up to 18,000 characters), a structured candidate profile, an in-prompt copy of the output schema, and a schema constraint to the model. The prompt requests 10–18 material requirements and can expand to 25; the call permits 2,400 output tokens and an 8,192-token context. A successful result is cached by job/profile/provider/model/cache-version, which is good, but the first analysis can still be unnecessarily expensive for a quick apply/no-apply decision.

### Cover letters and application answers

`backend/app/services/application_drafts.py` includes up to 16,000 characters of sanitized CV text and up to 24,000 characters of job text when drafting a cover letter. It allows 3,000 output tokens with a 16,384-token context, even though the requested letter is only 280–350 words. If the draft fails its quality gate, it performs a second full generation with the same large source text. This is a credible cause of long waits with a slow local model or a rate-limited provider.

### Provider layer and perceived latency

`backend/app/services/ai_provider.py` makes non-streaming calls, so the UI waits for the full result. Hosted OpenAI-compatible calls use a 90-second timeout and two SDK retries; retries are useful for transient errors but can extend the perceived wait substantially when a request fails. The provider layer does not currently expose per-call duration, prompt size, response size, or retry timing in a way that makes slow requests easy to diagnose.

### Existing optimizations worth preserving

- Ollama is configured as the default local provider with `qwen3:4b` and `think=False`.
- Successful match analyses are cached.
- Cloud match calls use a bounded pool of up to four workers; Ollama matching is serial to reduce load on the local machine.
- Hosted-provider data-sharing consent is required in the settings flow.
- CV extraction, matching, and drafting share the same provider layer.

These are useful foundations, so the next change should optimize their behavior instead of replacing the architecture.

## Recommended provider strategy

### 1. First hosted provider to benchmark: Groq's OpenAI-compatible API

Groq documents compatibility with the OpenAI Python client, using `https://api.groq.com/openai/v1`, and publishes model-specific rate limits. Its current model list includes high-throughput models such as `openai/gpt-oss-20b`; the exact free-plan access and limits should be confirmed in the account console before relying on a model. This is the first hosted provider I would benchmark for quick text-only matching and drafting because it fits CareerMate's existing OpenAI-compatible adapter and is designed for fast inference.

Use a provider API key stored only in `backend/.env`; select **OpenAI-compatible API** in CareerMate, set the URL and currently available model ID, acknowledge cloud data sharing, and run the provider test. The app stores only provider/model/base URL in JSON; do not paste a secret into the frontend or commit `.env`.

### 2. Gemini is already reachable through the existing compatible-provider path

Google currently documents an OpenAI-compatible Gemini endpoint at `https://generativelanguage.googleapis.com/v1beta/openai/` and shows `gemini-3.8-flash` in its examples. A dedicated Gemini code path is not required just to try a text model: use the existing OpenAI-compatible provider and verify that the selected model returns the JSON mode CareerMate expects. Model availability and per-project RPM/TPM/RPD limits change, so check the active quota in Google AI Studio rather than relying on a generic quota number.

Important privacy trade-off: Google's current pricing page says content in the Gemini API free tier may be used to improve Google products; paid-tier content is treated differently. Avoid sending an unredacted personal CV to a free-tier hosted service unless you accept that policy. CareerMate does not need to upload a CV file directly for these text tasks: it extracts text locally and places the relevant text in the prompt, which still consumes input tokens and sends that text to the provider.

### 3. OpenRouter is a backup/testing option, not a guaranteed unlimited free backend

OpenRouter can route among many models through one API, but free model variants are subject to platform-level limits and upstream providers can independently return rate-limit/capacity errors. It is useful for testing model quality and selecting fallbacks, but don't assume an unlimited daily allowance or uninterrupted free capacity.

### 4. Keep Ollama for private/offline work, but benchmark smaller models

Ollama remains the no-API-bill and privacy-preserving option. The Ollama Qwen3 library lists `qwen3:4b` at about 2.5 GB download and `qwen3:1.7b` at about 1.4 GB; those are download sizes, not total RAM requirements. Test the existing `qwen3:4b` and a smaller quantized model on the actual Windows machine using the same saved job/profile. Compare latency and evidence quality, not just whether it returns output. Keep hosted providers optional because local inference is the best default for CV privacy.

### 5. Hugging Face's routed inference free allowance is very small for daily use

Hugging Face currently documents $0.10 of monthly routed Inference Provider credits for free users, subject to change. That is useful for experiments but is not a realistic main provider for processing a large batch of job applications every day.

## Implementation order

1. **Instrument before tuning.** Record elapsed time for CV analysis, each job match, and each application draft; log provider/model, approximate input characters, returned characters/tokens when available, retries and error category. Never log prompt contents, CV content, API keys, or contact information.
2. **Introduce fast and detailed analysis modes.** Fast mode should target a decision: short list of the most important advertised requirements, concise evidence snippets and a compact JSON response. Detailed mode can request a more exhaustive 15–25 requirement review after a job passes the first screen.
3. **Reduce repeated context.** Reuse the saved structured profile; prepare a concise professional summary and relevant experience excerpts once. Send only relevant job-ad sections instead of large full-text prefixes wherever possible. Avoid embedding a schema both as verbose prompt text and as a structured-output parameter if the provider supports the structured parameter.
4. **Right-size output limits.** A 280–350-word letter normally needs far fewer than 3,000 generated tokens. Benchmark a 700–1,000-token ceiling for letters and a compact 800–1,400-token ceiling for fast matching. Keep limits configurable and verify that quality gates still work.
5. **Make quality repair cheap.** Preserve a single quality gate, but have a narrowly scoped repair request fix the failed criterion (e.g. add a missing body paragraph) rather than regenerate the full letter from all the source material. Only use one bounded repair attempt.
6. **Set explicit timeout/retry budgets.** Don't let SDK retries plus application-level repair loops stack into minutes of waiting. Retry only transient errors such as 429/5xx/timeouts, respect provider retry hints, and return a clear actionable error otherwise.
7. **Use progressive UX.** Add stages such as “Preparing job details”, “Analyzing requirements”, and “Checking evidence”; stream cover-letter tokens where supported and show completed job matches as they arrive. Streaming improves perceived wait time even when total inference time is unchanged.
8. **Control concurrency by provider.** Keep local Ollama conservative. For online providers, benchmark two concurrent matches before enabling four, because token-per-minute limits can be exhausted by several large prompts at once. Keep provider fallback opt-in and ensure a fallback never silently sends personal data to a new host.
9. **Add regression tests and a benchmark fixture.** Use one short and one long job advert with a fixed synthetic profile. Measure cold and warm cache paths, verify output shape/quality, test 429 and timeout handling, and compare model decisions to known expected evidence.

## Suggested acceptance measures

These are targets to measure, not guarantees about current performance:

- Cached match: effectively immediate from local storage, without another model call.
- Hosted fast match: median under 5 seconds after the prompt is compacted, measured over at least 20 representative jobs.
- Hosted cover letter: first complete draft within about 10 seconds in a repeatable test, with quality repair measured separately.
- Local model: record real cold-start and warm-run latency on the user's machine before selecting a target.
- Accuracy: maintain tests proving that explicit saved location/language facts are not lost, missing evidence is not treated as proof of lack, and no fabricated credentials appear in drafts.
- Reliability: report rate limits and timeouts clearly rather than spinning/retrying for several minutes.

## Repository blocker discovered during this review

The uploaded snapshot's `backend/app/main.py` imports `app.models.application`, `app.models.browser_assistance`, `app.models.ai`, and `app.models.data_management`, but those files are absent from `backend/app/models/` in this ZIP. As a result, the full backend tests cannot be collected and the API cannot import normally in this snapshot. The five isolated tests in `backend/tests/test_job_search_regression.py` do pass when run with `PYTHONPATH=backend`. Restore or recreate the missing model modules as a separate prerequisite before implementing and validating AI runtime changes.

## Official references checked on 11 October 2026

- [Gemini pricing and free-tier data usage](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [Groq supported models](https://console.groq.com/docs/models)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [OpenRouter API limits](https://openrouter.ai/docs/api_reference/limits)
- [Hugging Face Inference Provider pricing](https://huggingface.co/docs/inference-providers/pricing)
- [Ollama Qwen3 models and sizes](https://ollama.com/library/qwen3/tags)
- [Ollama API options](https://github.com/ollama/ollama/blob/main/docs/api.md)
