# Browser setup and local data management

## Fix “Could not open the visible browser”

CareerMate uses Playwright with a locally installed Chromium binary. Installing the Python package does not always install the browser binary automatically.

From PowerShell, use the same virtual environment that runs Uvicorn:

```powershell
cd C:\CareerMate\backend
.\.venv\Scripts\Activate.ps1
python -m playwright install chromium
```

Restart Uvicorn afterward. You can also use **Applications → Check Playwright / Chromium**. The diagnostics endpoint is `GET /api/browser/diagnostics`; it checks whether Playwright and its Chromium executable are available without opening a browser or visiting a website.

If Playwright and Chromium are both reported as installed but a page still fails to open, the browser launched but the public listing may have failed to load. Check the saved job URL by opening it in your regular browser and verify network connectivity. Some employers block automated browser contexts or require manual sign-in; CareerMate does not bypass those controls.

## Data management

The **Data management** page reports counts only; it does not display private CV contents.

- **Clear caches** removes the match cache and fetched public job-source caches. It keeps the current CV, extracted text, profile, saved jobs, application records, and preferences.
- **Clean everything** requires typing `DELETE ALL LOCAL DATA`. It closes the visible browser session and removes all non-template files under `data/`: current CV and extracted text, profile, saved jobs, match cache, source cache, application tracker, AI preferences, and `sources.json` configuration. Example files ending in `.example.json` and `.gitkeep` placeholders are preserved.

The reset operates only inside the project's `data/` directory. It does not remove `backend/.env` (including API keys), source code, installed packages, or the Python virtual environment. It is permanent; back up data first if any information may be needed later.

API routes:

- `GET /api/data/summary`
- `POST /api/data/clear-cache`
- `POST /api/data/reset` with JSON body `{"confirmation":"DELETE ALL LOCAL DATA"}`
