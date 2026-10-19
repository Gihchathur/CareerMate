# Security policy

CareerMate is a local-first personal application and is not designed to be exposed directly to the public internet. It has no built-in account authentication.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository if it is enabled. Otherwise, open a public issue without including exploit details or personal data and ask for a private reporting channel.

## Data handling

Do not include CVs, personal profiles, API keys, browser storage state, or live application details in bug reports. Hosted AI providers receive the task text required for the requested operation after the user enables consent.

## Browser automation

Browser-assisted features visit employer pages. Keep the application on localhost, install updates, and do not disable public-URL validation or browser safety checks. Docker Compose binds the UI to loopback by default; changing that binding requires a separate authentication and security review.
