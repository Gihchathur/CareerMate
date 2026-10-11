# Full job analysis and cover-letter quality

## Why the enrichment step exists

Aggregators and search feeds frequently store a short teaser rather than the complete employer advert. Matching a CV against that teaser creates a deceptively precise score and can hide eligibility constraints. CareerMate therefore tries to fetch a fuller advert from the saved public listing URL before calculating a match.

## Refresh the full advert

- From **Find jobs**, open a listing and use **Fetch full job description**.
- From **Match insights**, use **Fetch full advert & reanalyse** when the report is marked preliminary.
- From **Applications**, fetch/refresh the full description in the tracked application before drafting a letter.

The enrichment service only accesses public HTTPS pages. It rejects unsafe/private-network URLs, follows redirects only after revalidating destinations, caps the response size, and parses server-rendered HTML plus `JobPosting` JSON-LD. It doesn't execute JavaScript, authenticate, solve CAPTCHAs, work around bot protections, or bypass access controls. If a page is rendered client-side or denies public access, open the source yourself and review/copy the relevant description into the existing saved-job details where supported.

If no full advert is available, the match is marked preliminary rather than being presented as a decision-ready score. Enrichment is best-effort; a source page may change, block requests, or expose only partial structured text.

## How to read the requirement analysis

CareerMate asks the selected AI provider to review the full description and extract up to 40 distinct material criteria. It should cover:

- Required and preferred skills/tools, responsibilities, seniority and years of experience.
- Education, certifications and domain/product experience where the employer requests them.
- Location, on-site/hybrid constraints, language requirements, work eligibility and other explicit hiring constraints.
- The employer's optional/nice-to-have criteria separately from hard requirements.

Each criterion is assessed as **supported**, **partially supported**, or **not evidenced**, with short quoted evidence when possible. The review highlights critical gaps separately. Explicit hard thresholds (for example, a stated minimum number of years) can be marked critical; a clearly optional language or skill should not be treated as a blocker.

These are AI-assisted interpretations, not definitive eligibility decisions. Check the original advert. A `not_evidenced` status means the current CV/profile does not demonstrate the item; it doesn't automatically mean the candidate doesn't have it. A green supported item doesn't guarantee an employer will consider it sufficient.

## Cover-letter generation

CareerMate supplies the draft generator with the reviewed professional profile, redacted text extracted from the current CV, and the saved job-description text. It excludes email, phone, and contact URLs from the candidate prompt. The prompt targets approximately 280–350 words, usually four or five purposeful body paragraphs plus greeting and sign-off, tailored to the employer's actual product and responsibilities.

A quality gate rejects letters shorter than 220 words, longer than 420 words, or with fewer than four separated paragraphs. It retries once and raises an error rather than saving a still-incomplete draft. This validates length and structure only; it cannot guarantee that every claim is accurate or every sentence is good. Review and edit the content before use.

If the application record only contains a short teaser (fewer than 500 characters) and a public full advert could not be retrieved, the API blocks cover-letter generation with HTTP 409 and asks the user to fetch/review the full advert first. This avoids writing a generic two-sentence letter against missing requirements.

## Privacy

With Ollama, inference stays on the configured Ollama host. With Gemini or another hosted provider, task-specific CV and job text leaves the computer. Review that provider's terms before sending personal data; do not send a real identifiable CV through a free service if its terms permit human review or product-improvement use. API credentials must stay in environment variables, not job JSON, source code, or frontend settings.

## Regression tests

`tests/test_job_details_and_quality.py` and `tests/test_applications.py` cover public-page enrichment, fuller URL selection, provisional scoring when only a snippet exists, criticality handling, CV contact redaction, insufficient-description blocking, and short/poorly structured cover-letter retries. Tests mock AI and remote HTTP; live provider connectivity and live job-page extraction still need manual verification in your environment.
