# Privacy and browser safety

CareerMate is a local-first personal workspace. It stores the candidate profile, CV upload/text, saved jobs, application drafts, settings and caches under `data/` (excluding API credentials, which belong in `backend/.env`). Treat the data directory as private personal data.

## Git and backups

- `backend/.env` and frontend environment files must never be committed.
- Do not commit `data/cv/current.pdf`, extracted CV text, `data/cv/profile.json`, `data/jobs/jobs.json`, `data/applications/applications.json`, `data/sources.json`, or anything under `data/source_cache/`.
- Only commit synthetic `*.example.json` samples and `.gitkeep` markers.
- Before publishing issue screenshots or logs, redact names, email/phone, job applications, browser URLs and tokens.
- Back up the local `data/` directory securely; it is not encrypted by CareerMate.

## Hosted AI

Ollama can keep inference local when hosted on your machine. OpenAI and OpenAI-compatible providers receive the text necessary for the action you request. Do not send confidential information unless you have reviewed that provider's terms and enabled the corresponding consent in CareerMate.

## Browser automation boundaries

CareerMate's browser helper is designed for supported public HTTPS pages. It blocks known unsupported job platforms and rejects non-public network destinations. It must not bypass login, MFA, CAPTCHA, access controls, bot detection or rate limits. Do not use saved browser sessions from another person. Review proposed application answers, especially work authorization, salary, legal statements, diversity disclosures, certifications and other sensitive facts.

The final application submission is a consequential external action and requires a separate explicit approval. If the site presents an unsupported control, a security challenge or a required fact that CareerMate cannot establish from the profile, complete that step manually.

## Docker exposure

The bundled Compose setup binds the frontend to `127.0.0.1:8080` by default and stores data in a host-mounted directory. It does not include authentication. Do not change the binding to `0.0.0.0` or publish the service to the internet without implementing authentication, authorization, CSRF protections and a reviewed security model.
