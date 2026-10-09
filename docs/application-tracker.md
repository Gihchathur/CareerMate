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

Drafts are generated through the configured local Ollama instance. The generation prompt includes the profile's professional facts and the job description snapshot but excludes email, phone, and profile links. It instructs the model not to fabricate experience, accomplishments, qualifications, metrics, or authorization, and treats job/profile text as untrusted input. These prompt constraints reduce risk but cannot guarantee factual correctness, so the UI explicitly asks the user to review the result. Generated text is never submitted automatically.

## Tests

`tests/test_applications.py` covers one-record-per-job behavior, saved-job validation, local persistence, valid application stage updates, invalid stage rejection, missing-profile errors, local prompt contact-data exclusion, and persistence of generated drafts. The model-inference tests use a fake Ollama client; live model generation still depends on Ollama being installed and running locally.
