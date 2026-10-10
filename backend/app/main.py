import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.models.candidate import CandidateProfile
from app.models.application import (
    ApplicationAnswer, ApplicationCreateRequest, ApplicationRecord, ApplicationUpdateRequest,
    DraftAnswerRequest,
)
from app.models.browser_assistance import BrowserFillRequest
from app.models.ai import AIProviderTestRequest, AISettingsUpdate
from app.services.ai_provider import (
    AIProviderError, get_active_provider_identity, get_ai_settings, save_ai_settings, test_provider_connection,
)
from app.services.browser_assistance import (
    BrowserAssistanceError,
    close_browser_session,
    fill_reviewed_fields,
    get_browser_session_status,
    open_application_page,
    scan_current_form,
)
from app.services.cv_analyzer import CVAnalyzerError, analyze_cv
from app.services.application_drafts import (
    DraftGenerationError, generate_application_answer, generate_cover_letter,
)
from app.services.application_storage import (
    create_application, load_applications, update_application, utc_now,
)
from app.services.cv_parser import CVParserError, extract_cv_text
from app.services.job_matcher import score_job
from app.services.job_discovery import JobDiscoveryError, search_multiple_roles
from app.services.job_sources.base import JobSourceError
from app.services.job_search import source_status
from app.services.job_storage import load_saved_jobs, save_jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Release the visible browser session cleanly when the local API stops."""
    yield
    await close_browser_session()


app = FastAPI(
    title="CareerMate API",
    description="Local-first job search and application assistant",
    version="0.7.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CV_DIR = DATA_DIR / "cv"
JOBS_DIR = DATA_DIR / "jobs"
APPLICATIONS_DIR = DATA_DIR / "applications"
PROFILE_PATH = CV_DIR / "profile.json"
EXTRACTED_TEXT_PATH = CV_DIR / "extracted_text.txt"

CV_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)
APPLICATIONS_DIR.mkdir(parents=True, exist_ok=True)

MAX_CV_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
DEFAULT_WEB_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CAREERMATE_CORS_ORIGINS", ",".join(DEFAULT_WEB_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


@app.get("/api/ai/settings")
def read_ai_settings() -> dict[str, object]:
    """Return active provider/model settings without exposing API credentials."""
    return get_ai_settings()


@app.put("/api/ai/settings")
def update_ai_settings(request: AISettingsUpdate) -> dict[str, object]:
    try:
        return save_ai_settings(
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
            confirm_cloud_data_sharing=request.confirm_cloud_data_sharing,
        )
    except AIProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ai/test")
def test_ai_settings(request: AIProviderTestRequest) -> dict[str, object]:
    """Check a provider with a short, non-personal prompt; does not save settings."""
    try:
        return test_provider_connection(request.provider, request.model, request.base_url)
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "CareerMate"}


@app.get("/api/cv/status")
def get_cv_status() -> dict[str, object]:
    has_text = EXTRACTED_TEXT_PATH.exists()
    try:
        character_count = len(EXTRACTED_TEXT_PATH.read_text(encoding="utf-8")) if has_text else 0
    except OSError:
        character_count = 0
    return {
        "uploaded": has_text and character_count > 0,
        "extracted_text_characters": character_count,
        "profile_saved": PROFILE_PATH.exists(),
    }


@app.post("/api/cv/upload")
async def upload_cv(file: UploadFile) -> dict[str, object]:
    """Validate, parse and save a CV without replacing valid data on failure."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Supported formats: PDF, DOCX and TXT.")

    temporary_upload = CV_DIR / f"upload-{uuid4().hex}{extension}"
    try:
        contents = await file.read(MAX_CV_UPLOAD_BYTES + 1)
        if not contents:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        if len(contents) > MAX_CV_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"The CV exceeds the {MAX_CV_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
            )

        temporary_upload.write_bytes(contents)
        text = extract_cv_text(temporary_upload)
        if not text:
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted. The document may be scanned or image-only.",
            )

        destination = CV_DIR / f"current{extension}"
        temporary_upload.replace(destination)
        temporary_text = CV_DIR / f"extracted-{uuid4().hex}.tmp"
        temporary_text.write_text(text, encoding="utf-8")
        temporary_text.replace(EXTRACTED_TEXT_PATH)

        # A new CV invalidates the old structured profile so it cannot be
        # accidentally used for matching before it is analyzed again.
        PROFILE_PATH.unlink(missing_ok=True)
        for old_extension in ALLOWED_EXTENSIONS - {extension}:
            (CV_DIR / f"current{old_extension}").unlink(missing_ok=True)

        return {
            "success": True,
            "filename": Path(file.filename).name,
            "format": extension,
            "characters": len(text),
            "message": "CV uploaded and text extracted locally.",
        }
    except CVParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except OSError as exc:
        logger.exception("Could not save uploaded CV")
        raise HTTPException(status_code=500, detail="Could not save the CV locally.") from exc
    finally:
        await file.close()
        temporary_upload.unlink(missing_ok=True)


@app.post("/api/cv/analyze")
def analyze_uploaded_cv() -> dict[str, object]:
    try:
        profile = analyze_cv()
        return {"success": True, "profile": profile.model_dump()}
    except CVAnalyzerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/cv/profile")
def get_candidate_profile() -> dict[str, object]:
    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=404, detail="No candidate profile found. Analyze your CV first.")
    try:
        profile = CandidateProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))
        return {"success": True, "profile": profile.model_dump()}
    except (OSError, ValidationError, ValueError) as exc:
        logger.exception("Could not load saved candidate profile")
        raise HTTPException(status_code=500, detail="The saved profile is invalid or unreadable.") from exc


@app.put("/api/cv/profile")
def save_candidate_profile(profile: CandidateProfile) -> dict[str, object]:
    _atomic_write(PROFILE_PATH, profile.model_dump_json(indent=2))
    return {
        "success": True,
        "message": "Candidate profile saved locally.",
        "profile": profile.model_dump(),
    }


@app.get("/api/jobs/search")
def search_job_listings(
    roles: list[str] = Query(default=[]),
    query: str | None = Query(default=None, min_length=2, max_length=100),
    country: str = Query(default="Sweden", max_length=80),
    city: str = Query(default="", max_length=100),
    location: str = Query(default="", max_length=100),
    work_mode: Literal["any", "remote", "hybrid", "on_site"] = Query(default="any"),
    sources: list[str] | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=40),
    offset: int = Query(default=0, ge=0, le=2000),
) -> dict[str, object]:
    """Search one or more roles, apply transparent local filters, and save results."""
    role_values = roles or ([query] if query else [])
    effective_city = city.strip() or location.strip()

    try:
        result = search_multiple_roles(
            roles=role_values,
            country=country,
            city=effective_city,
            work_mode=work_mode,
            limit=limit,
            sources=sources,
            offset=offset,
        )
        jobs = result["jobs"]
        job_payload = [job.model_dump() for job in jobs]  # type: ignore[union-attr]
        saved_total = save_jobs(job_payload)

        return {
            "success": True,
            **{key: value for key, value in result.items() if key != "jobs"},
            "saved_total": saved_total,
            "jobs": job_payload,
        }
    except JobDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except JobSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Could not save job search results")
        raise HTTPException(status_code=500, detail="Could not save job listings locally.") from exc


@app.get("/api/jobs/sources")
def get_job_sources() -> dict[str, object]:
    """Report which job sources are configured without exposing credentials."""
    try:
        return {"success": True, "sources": source_status()}
    except JobSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs")
def get_saved_job_listings() -> dict[str, object]:
    try:
        jobs = load_saved_jobs()
        return {"success": True, "total": len(jobs), "jobs": jobs}
    except RuntimeError as exc:
        logger.exception("Could not load saved jobs")
        raise HTTPException(status_code=500, detail="Could not load saved job listings.") from exc


@app.get("/api/applications")
def get_applications() -> dict[str, object]:
    """List the local application tracker records."""
    try:
        records = load_applications()
    except RuntimeError as exc:
        logger.exception("Could not load application records")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    status_counts: dict[str, int] = {}
    for item in records:
        status = str(item.get("status", "saved"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "success": True,
        "total": len(records),
        "status_counts": status_counts,
        "applications": records,
    }


@app.post("/api/applications")
def add_application(request: ApplicationCreateRequest) -> dict[str, object]:
    """Add a saved job to the tracker, idempotently."""
    try:
        saved_jobs = load_saved_jobs()
        job = next((item for item in saved_jobs if str(item.get("id", "")) == request.job_id), None)
        if job is None:
            raise HTTPException(
                status_code=404,
                detail="This job is not in your saved jobs yet. Search for it again before tracking it.",
            )

        now = utc_now()
        job_url = str(job.get("apply_url") or job.get("source_url") or "")
        if not job_url.startswith(("https://", "http://")):
            job_url = ""
        record = ApplicationRecord(
            id=f"application:{uuid4().hex}",
            job_id=request.job_id,
            company=str(job.get("company", ""))[:300],
            title=str(job.get("title", ""))[:500],
            location=str(job.get("location", ""))[:300],
            source=str(job.get("source", ""))[:100],
            job_url=job_url[:2000],
            job_description=str(job.get("description", ""))[:30000],
            status="saved",
            notes=request.notes,
            created_at=now,
            updated_at=now,
        ).model_dump()
        saved_record, created = create_application(record)
        return {
            "success": True,
            "created": created,
            "message": "Added to your application tracker." if created else "This job is already in your application tracker.",
            "application": saved_record,
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.exception("Could not create application record")
        raise HTTPException(status_code=500, detail="Could not save the application locally.") from exc


@app.put("/api/applications/{application_id}")
def edit_application(
    application_id: str,
    request: ApplicationUpdateRequest,
) -> dict[str, object]:
    """Save reviewed status, notes, follow-up dates and edited drafts."""
    try:
        updates = request.model_dump(exclude_unset=True, exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No application changes were provided.")
        if updates.get("status") == "applied":
            records = load_applications()
            existing = next((item for item in records if item["id"] == application_id), None)
            if existing is None:
                raise HTTPException(status_code=404, detail="Application record not found.")
            if not existing.get("applied_at"):
                updates["applied_at"] = utc_now()
        saved_record = update_application(application_id, updates)
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.exception("Could not update application record")
        raise HTTPException(status_code=500, detail="Could not update the application locally.") from exc

    if saved_record is None:
        raise HTTPException(status_code=404, detail="Application record not found.")
    return {"success": True, "application": saved_record, "message": "Application updated locally."}


def _load_draft_inputs(application_id: str) -> tuple[ApplicationRecord, CandidateProfile]:
    try:
        if not PROFILE_PATH.exists():
            raise HTTPException(
                status_code=400,
                detail="Review and save your CV profile before generating application drafts.",
            )
        profile = CandidateProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))
        applications = load_applications()
        record = next((item for item in applications if item["id"] == application_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Application record not found.")
        return ApplicationRecord.model_validate(record), profile
    except HTTPException:
        raise
    except (OSError, ValidationError, ValueError, RuntimeError) as exc:
        logger.exception("Could not load application draft inputs")
        raise HTTPException(status_code=500, detail="Could not load the profile or application record.") from exc


@app.post("/api/applications/{application_id}/draft-cover-letter")
def draft_cover_letter(application_id: str) -> dict[str, object]:
    """Generate and persist a reviewable cover-letter draft using the selected AI provider."""
    application, profile = _load_draft_inputs(application_id)
    try:
        content = generate_cover_letter(application, profile)
        updated = update_application(application_id, {"cover_letter": content})
        if updated is None:
            raise HTTPException(status_code=404, detail="Application record not found.")
        return {
            "success": True,
            "message": "Cover-letter draft generated. Review it carefully before using it.",
            "application": updated,
        }
    except DraftGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Could not save cover-letter draft")
        raise HTTPException(status_code=500, detail="Could not save the generated draft locally.") from exc


@app.post("/api/applications/{application_id}/draft-answer")
def draft_application_answer(
    application_id: str,
    request: DraftAnswerRequest,
) -> dict[str, object]:
    """Generate and persist an answer draft for one employer question."""
    application, profile = _load_draft_inputs(application_id)
    try:
        answer_text = generate_application_answer(application, profile, request.question)
        records = [item for item in application.answers if item.question.casefold() != request.question.casefold()]
        if len(records) >= 50:
            raise HTTPException(
                status_code=400,
                detail="This application has reached the 50-answer limit. Remove an old answer before adding another.",
            )
        records.append(ApplicationAnswer(question=request.question, answer=answer_text, updated_at=utc_now()))
        updated = update_application(application_id, {"answers": [item.model_dump() for item in records]})
        if updated is None:
            raise HTTPException(status_code=404, detail="Application record not found.")
        return {
            "success": True,
            "message": "Answer draft generated. Review it before submitting.",
            "application": updated,
        }
    except HTTPException:
        raise
    except DraftGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Could not save application answer")
        raise HTTPException(status_code=500, detail="Could not save the answer draft locally.") from exc


@app.post("/api/applications/{application_id}/browser/open")
async def open_application_browser(application_id: str) -> dict[str, object]:
    """Open a visible local browser at the tracked role's HTTPS listing/application link."""
    try:
        records = load_applications()
        record = next((item for item in records if item.get("id") == application_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Application record not found.")
        target_url = str(record.get("job_url", "")).strip()
        if not target_url:
            raise HTTPException(status_code=400, detail="This application does not have a public job URL.")
        return await open_application_page(application_id, target_url)
    except HTTPException:
        raise
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/browser/session")
async def browser_session_status() -> dict[str, object]:
    return await get_browser_session_status()


@app.post("/api/browser/scan")
async def scan_application_form() -> dict[str, object]:
    try:
        return await scan_current_form()
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/applications/{application_id}/browser/fill")
async def fill_application_form(
    application_id: str,
    request: BrowserFillRequest,
) -> dict[str, object]:
    """Fill only the fields the user selected and reviewed in the application workspace."""
    try:
        fields = [item.model_dump() for item in request.fields]
        return await fill_reviewed_fields(application_id, fields)
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/browser/session")
async def end_browser_session() -> dict[str, object]:
    return await close_browser_session()


@app.get("/api/jobs/matches")
def get_job_matches(
    limit: int = Query(default=5, ge=1, le=20),
    job_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    """Analyze at most `limit` saved jobs, using the configured AI provider."""
    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=404, detail="Analyze and save your CV profile first.")

    try:
        profile = CandidateProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))
        saved_jobs = load_saved_jobs()
    except (OSError, ValidationError, ValueError, RuntimeError) as exc:
        logger.exception("Could not load matching inputs")
        raise HTTPException(status_code=500, detail="Could not load the candidate profile or saved jobs.") from exc

    if job_ids is not None:
        # Honor the currently displayed job cards instead of accidentally
        # analyzing unrelated jobs left by older searches.
        by_id = {str(job.get("id", "")): job for job in saved_jobs}
        selected_jobs = [by_id[item] for item in job_ids[:limit] if item in by_id]
    else:
        selected_jobs = saved_jobs[:limit]

    results: list[dict[str, object]] = []
    profile_data = profile.model_dump()
    provider, model = get_active_provider_identity()

    def analyze_one(job: dict[str, object]) -> dict[str, object]:
        match = score_job(job, profile_data)
        return {**job, **match}

    # Local Ollama is deliberately sequential to avoid putting more pressure on
    # the user's machine. Hosted API calls run in a small bounded pool to reduce
    # wall-clock time. The worker count is bounded to avoid runaway API spend.
    if provider != "ollama" and len(selected_jobs) > 1:
        workers = min(4, len(selected_jobs))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="careermate-ai") as executor:
            results = list(executor.map(analyze_one, selected_jobs))
    else:
        results = [analyze_one(job) for job in selected_jobs]

    results.sort(
        key=lambda item: (
            item.get("match_score") is None,
            -(item.get("match_score") if isinstance(item.get("match_score"), (int, float)) else 0),
        )
    )
    return {
        "success": True,
        "total_saved": len(saved_jobs),
        "analyzed": len(results),
        "requested_job_ids": len(job_ids) if job_ids is not None else 0,
        "limit": limit,
        "method": f"{provider}_llm_evidence_weighted_v3",
        "provider": provider,
        "model": model,
        "concurrency": min(4, len(selected_jobs)) if provider != "ollama" else 1,
        "jobs": results,
    }
