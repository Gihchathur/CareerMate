# Application tracker and draft assistant (Step 12)

## User workflow

1. Search for a job and open its details drawer.
2. Choose **Add to application tracker**. CareerMate snapshots the saved listing into a local application record. A job can only be tracked once; choosing the action again opens the existing record.
3. Select the application in the **Applications** workspace. Keep notes and a follow-up date, and update the application stage. Saving the `applied` stage records `applied_at` if it does not already exist.
4. Optionally generate a cover-letter draft or draft an answer to a pasted employer question. Edit the text and save changes before using it.
5. Open the original employer listing and submit manually. CareerMate does not automate or submit applications.

## Local storage

The application tracker stores all records in `data/applications/applications.json`. The file is created on the first tracked job; a missing file is treated as an empty tracker. Writes validate each record and atomically replace the JSON file. Records are deduplicated by `job_id`. There is no SQL database or remote application backend.

Each record snapshots the job ID, company, title, location, source, URL, and description alongside the status, notes, follow-up date, cover letter, saved answers, and timestamps. This protects existing application work if the saved-job list later changes.

## API

- `GET /api/applications` returns records plus counts by status.
- `POST /api/applications` accepts `{ "job_id": "...", "notes": "..." }`. It returns the existing record if this job is already tracked.
- `PUT /api/applications/{application_id}` updates `status`, `notes`, `follow_up_date`, `cover_letter`, and/or `answers`.
- `POST /api/applications/{application_id}/draft-cover-letter` creates and stores a cover-letter draft.
- `POST /api/applications/{application_id}/draft-answer` accepts `{ "question": "..." }` and replaces the saved answer when the same question is submitted again.

## Draft safety and privacy

Drafts use the AI provider selected in **AI provider**. Cover letters use the reviewed professional profile, sanitized text extracted from the current CV, and the saved job-description snapshot. Direct contact channels are redacted from the extracted CV text and excluded from the professional-profile payload. The prompt requests a role-specific letter of approximately 280–350 words in multiple purposeful paragraphs and grounds candidate claims only in the CV/profile. A quality gate retries very short, overlong, or one-block responses once, then refuses to save the result if it still fails the completeness threshold. Draft generation is blocked when only a very short search snippet is available; fetch the full public employer advert first. Employer-question answers use the same selected provider and must be reviewed. These checks reduce risk but cannot guarantee factual correctness. Hosted providers receive task-specific text outside the computer, so review the provider's privacy terms and do not send sensitive data to an unsuitable free tier. Generated text is never submitted automatically.

## Tests

`tests/test_applications.py` covers one-record-per-job behavior, saved-job validation, local persistence, valid application stage updates, invalid stage rejection, missing-profile errors, local prompt contact-data exclusion, and persistence of generated drafts. The model-inference tests mock provider responses; live generation requires the selected provider to be configured and reachable.
