# CareerMate

CareerMate is a local-first, open-source job discovery and CV-matching workspace. It searches a public Swedish job data source, extracts a candidate profile from a CV, and uses a local Ollama model to compare job requirements against evidence in that profile.

## Current capabilities

- Read PDF, DOCX, and TXT CVs locally.
- Extract a structured candidate profile using Ollama.
- Review and edit the profile before matching.
- Search Arbetsförmedlingen's public JobAd Links API.
- Save normalized job listings in local JSON files.
- Compare selected jobs to the profile using a local model and show evidence coverage.
- Cache successful match analyses locally to reduce repeated model calls.

Application form automation and application submission are not implemented in this version.

## Requirements

- Windows 10/11, macOS, or Linux
- Python 3.10+
- Node.js 20.19+ or 22.12+
- Ollama installed locally
- A compatible Ollama model pulled locally (default: `gemma4:e4b`)

## Run the backend

From the repository root, open PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API binds to `127.0.0.1:8000` by default. API documentation: <http://127.0.0.1:8000/docs>.

For a new PowerShell session on Windows, activate the virtual environment again before running the backend.

## Run the frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL Vite prints (normally <http://localhost:5173>).

The frontend can point to another local API URL by setting `VITE_API_URL` in `frontend/.env.local`, for example:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

The backend CORS origins can be configured with `CAREERMATE_CORS_ORIGINS`, as a comma-separated list. Do not bind the API to a public interface without adding an appropriate authentication and security design.

## Configure Ollama

The defaults are:

- `CAREERMATE_OLLAMA_HOST=http://127.0.0.1:11434`
- `CAREERMATE_OLLAMA_MODEL=gemma4:e4b`

Change these using environment variables if needed. For example in PowerShell:

```powershell
$env:CAREERMATE_OLLAMA_MODEL = "gemma4:e4b"
```

Ensure the model is available locally (`ollama list`). Model inference time depends on the model, available memory, and CV/job text length.

## Local data

User data is written under `data/`:

- `data/cv/current.*`: uploaded CV
- `data/cv/extracted_text.txt`: extracted CV text
- `data/cv/profile.json`: structured candidate profile
- `data/jobs/jobs.json`: saved job listings
- `data/jobs/match_cache.json`: successful match results

These files are ignored by Git. Only `.gitkeep` files and clearly synthetic `*.example.json` files should be committed. Never commit your actual CV, extracted text, saved profile, application answers, cookies, or browser state.

The UI does not call a cloud LLM. Job search sends the user's search terms to the public job source; it does not upload the CV. The selected job descriptions and a professional-only subset of the candidate profile are passed to Ollama on the configured local host for matching.

## Job data source

CareerMate currently uses the public Arbetsförmedlingen JobAd Links search API. Ads may contain brief descriptions and link to a separate provider's original listing. Always open the original listing to confirm that the job is current and review the complete requirements.

## Matching score

The match score is a weighted coverage estimate based on job requirements extracted by the local LLM and evidence found in the reviewed profile. It is not a probability of interview or offer. “Not evidenced” means the profile did not establish the requirement; it does not prove the candidate lacks it. Review the extracted requirements and evidence yourself.

## Tests

Install test dependencies:

```powershell
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt
```

From the repository root:

```powershell
$env:PYTHONPATH = "backend"
pytest
```

Frontend checks:

```powershell
cd frontend
npm run build
npm run lint
```

## Project principles

- Local-first storage; no SQL database.
- No bypassing CAPTCHA, MFA, bot detection, access controls, or rate limits.
- No automatic assessments, legal declarations, or unattended application submission.
- AI output is a draft and must be reviewed before use.
