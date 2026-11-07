# CareerMate 3.5.1 — Inbox freshness and navigation polish

## Changes

- Increased compact sidebar icons to 18px (16px on short windows, 15px on very short utility windows).
- Improved section separators and expanded-state group labels without adding a bulky sidebar or internal navigation scroll.
- Fixed Inbox data that could remain visible in React state after a full workspace reset.
- Inbox/activity GET requests now use browser `no-store` and server `Cache-Control: no-store` headers.
- Added request-generation protection so a delayed response from before a reset cannot restore deleted jobs.
- Returning to Inbox or Today re-fetches workflow state.
- The Data & Privacy page now explicitly explains that Clear caches preserves saved jobs; use Clean everything to remove saved jobs and empty the Inbox.
- Added reset regression coverage and isolated test source registries to prevent test runs from contacting live sample ATS portals.

## Windows update

1. Extract the release into a new folder.
2. Preserve your existing `backend/.env` and personal `data/` files if you do not intend to reset your workspace.
3. Install backend requirements only if your virtual environment does not already contain them:

   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

4. In a second PowerShell window:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

## Empty the Inbox

- **Clear caches** only removes derived source/match cache files. Saved jobs remain and continue to appear in the Inbox.
- **Clean everything** removes saved jobs, triage state, workflow activity, applications, candidate profile and local source/AI preferences from the workspace data folder. It preserves `backend/.env`, source code and the Python environment. This action is destructive and requires typing `DELETE ALL LOCAL DATA`.

After a successful full reset, the Inbox should report zero opportunities. If jobs remain, confirm the frontend is connected to the backend instance and `data/` directory you intended to reset.

## Verification

- `PYTHONPATH=backend pytest -q`: 166 passed.
- Python backend compilation: passed.
- FastAPI application import: passed (`CareerMate API 3.5.1`).
- TypeScript/TSX syntax transpilation: 15 files passed.
- CSS parsing: 26 stylesheets passed.
- A full Vite production build was not run because frontend npm dependencies were unavailable in the packaging environment.
