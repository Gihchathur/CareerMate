# Application automation

CareerMate can prepare supported multi-step applications in a Playwright browser session, but employer-specific markup and security controls mean coverage cannot be guaranteed for every site. It does not promise that every employer ATS is compatible; form markup, sign-in, required questions, and custom widgets differ by site.

## Workflow

1. Open the tracked application's employer link in CareerMate's visible Chromium session.
2. If an Apply/Start Application control is detected, choose **Find application form automatically**. CareerMate clicks one high-confidence public navigation control and scans the resulting step.
3. Review the current step. Name, contact, profile, saved cover-letter, and saved-answer fields can be suggested deterministically from the saved local profile and application record. Dropdowns and radio controls show their current allowed options. Checkbox choices are left unticked for approval.
4. Choose **Generate AI suggestions for questions** to draft open-ended answers in one request using the saved professional profile and the tracked job description. Nothing is filled by this AI action. AI output is added only to editable review boxes. CareerMate leaves salary, work authorization, visa/sponsorship, dates, legal consent, sensitive identifiers, and other personal decisions for the candidate.
5. Review/edit the proposed values. **Select all proposed values** checks the non-empty suggestions but deliberately does not check radio/checkbox decisions. Choose **Approve & fill this step** to fill only checked rows, or **Approve, fill & continue automatically** to fill the approved rows and click a detected safe Continue/Next/Review control.
6. Repeat for each step. If the page needs login, CAPTCHA, OTP, a custom widget, or manual verification, complete that part yourself in Chromium, then scan again.
7. On a page with a clear final Submit/Send/Complete Application control, review the employer form and attached CV. Tick the separate authorization checkbox and press **Submit application to employer**. The API refuses submission if the checkbox confirmation is false. It also refuses to click when CAPTCHA/security verification is detected, the form's native validation fails, or a unique final-submit control cannot be identified.
8. CareerMate marks the application as Applied only when it detects a likely employer confirmation message. Otherwise, check the live employer page before changing the tracker status manually.

## Multi-tab, cross-domain and embedded-form support

- The browser session uses one Playwright BrowserContext. When an Apply link opens a new tab or popup, CareerMate detects newly loaded pages in that same context and selects the newest loaded page for the next scan. Cookies/session state within that context follow the opened ATS page.
- A tab selector appears when more than one tab exists. It lets the user explicitly choose another tab if an ATS opens multiple tabs, keeps an original listing open, or the new tab was not the form.
- The scan iterates over eligible frames in the selected Page, not only the top document. Fields found inside a public HTTPS iframe receive globally unique field IDs and retain their frame index, so filling targets the frame where the field was found.
- CareerMate tries to dismiss only unambiguous optional-cookie choices such as “Reject optional cookies”, “Only necessary”, or “Essential only”. It does not click “Accept all” or make generic consent selections.
- **Auto prepare entire application** follows supported Apply/Continue steps, drafts answers for eligible open-ended questions in a batch per step, fills non-empty profile-backed/current/AI-drafted values, records visited steps, and stops at missing required fields, an unsupported next action, a repeated step, or the 12-step safety limit. It never clicks the final submit control.
- The preparation summary records what was filled. Controls for the currently active step remain editable. To change a prior step after preparation, use Chromium Back or choose the earlier tab, scan it again, and edit/refill it; not every single-page ATS preserves editable DOM for previous steps after navigation.

## Field coverage

- Text, email, phone, URL, search, date, number, and textarea inputs.
- HTML select menus.
- Radio groups and checkboxes, with the choices displayed in the review panel.
- Local `data/cv/current.pdf` attachment when the current control is clearly labelled CV/resume. The client cannot supply an arbitrary filesystem path.

Custom dropdowns implemented with non-standard elements, forms embedded in inaccessible cross-origin frames, or pages that change selectors dynamically may require manual intervention or future site-specific adapters.

Some ATS flows open the system browser or a separate Chromium process instead of a tab in CareerMate's BrowserContext; Playwright cannot automatically control those unrelated browser sessions. Authentication, OTP/CAPTCHA, bot challenges, legal consents, eligibility/sponsorship decisions, salary expectations, identity details, and unsupported widgets remain manual. Auto-prepare is intentionally capped and conservative: it may stop even if a human could continue rather than guess an answer or select a consequential option.

## Safety and privacy

- Browser assistance opens only publicly routable HTTPS links. Private/internal destinations are blocked, including redirected subresources.
- LinkedIn, Indeed, and Glassdoor automation remains blocked; use the employer's official career page instead.
- CareerMate never bypasses sign-in, anti-bot protection, CAPTCHA, OTP, or identity/security checks.
- Passwords, personal identity numbers, passport/credit-card/bank details, DOB, legal-consent controls, and non-CV file uploads are excluded.
- AI suggestions use the configured AI provider. Hosted providers require the existing explicit data-sharing consent in AI settings; the batch-suggestion endpoint does not bypass that check.
- Proposed field values are not persisted to CareerMate's JSON application tracker. They remain editable in the current app/browser session. Final application status is updated only after a likely confirmation is detected.
- Final submission is a separate action after the user explicitly authorizes it in the UI. The endpoint also requires a positive confirmation flag.

## Troubleshooting

- If the form is opened in a new tab or popup, choose it in the tab selector and rescan the page.
- If no supported fields are found, refresh the scan after the page has fully loaded and check whether the form is inside an accessible iframe.
- If Playwright fails on Windows with `NotImplementedError`, stop Uvicorn and run it without `--reload` while using browser assistance.
- If a form uses a custom widget or a separate external browser process, complete that portion manually.
- Review the live employer page after submission; a timeout or missing confirmation must not be interpreted as success.

## Privacy and safe-use boundaries

Browser preparation is intended for public job applications and employer-authorized use. CareerMate does not bypass authentication, MFA, CAPTCHA, bot detection, access controls or rate limits. Salary expectations, eligibility, sponsorship, legal declarations, identity data and other consequential answers require the candidate to decide. AI-drafted answers are suggestions and must be checked for accuracy.

Application fields are not saved into the local application tracker merely because they were scanned or drafted. Draft suggestions may be sent to the configured hosted AI provider only when cloud data-sharing consent is enabled. Final submission is a separate action that requires explicit confirmation.
