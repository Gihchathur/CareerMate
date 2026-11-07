import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError

from app.models.candidate import CandidateProfile
from app.models.candidate_evidence import CandidateEvidenceCreateRequest, CandidateEvidenceUpdateRequest
from app.models.application import (
    ApplicationAnswer, ApplicationCreateRequest, ApplicationRecord, ApplicationUpdateRequest,
    DraftAnswerRequest,
)
from app.models.browser_assistance import (
    BrowserFillRequest, BrowserNavigationRequest, BrowserPageSelectRequest, BrowserSuggestionRequest, BrowserSubmitRequest,
)
from app.models.ai import AIProviderTestRequest, AISettingsUpdate
from app.models.data_management import LocalDataResetRequest
from app.models.job import JobEnrichmentRequest
from app.models.workflow import JobTriageUpdateRequest
from app.services.ai_provider import (
    AIProviderError, get_active_provider_identity, get_ai_settings, save_ai_settings, test_provider_connection,
)
from app.services.browser_assistance import (
    BrowserAssistanceError,
    close_browser_session,
    fill_reviewed_fields,
    get_browser_session_status,
    get_browser_diagnostics,
    open_application_page,
    scan_current_form,
    advance_application_step,
    suggest_browser_answers,
    submit_reviewed_application,
    select_browser_page,
)
from app.services.cv_analyzer import CVAnalyzerError, analyze_cv
from app.services.resume_builder import create_tailored_cv, OUTPUT_DIR, list_tailored_versions
from app.services.platform_catalog import list_platforms
from app.services.resume_builder import export_tailored_pdf
from app.services.saved_searches import list_searches, save_search, delete_search, scan_alerts
from app.services.salary_normalizer import extract_salary
from app.services.alert_scheduler import start_scheduler, stop_scheduler
from app.services.saved_searches import list_alert_history, mark_alert_read, record_alerts
from app.services.application_drafts import (
    DraftGenerationError, generate_application_answer, generate_cover_letter,
)
from app.services.candidate_evidence_storage import create_evidence, delete_evidence, load_evidence, update_evidence
from app.services.application_storage import (
    create_application, load_applications, update_application, utc_now,
)
from app.services.cv_parser import CVParserError, extract_cv_text
from app.services.job_matcher import score_job
from app.services.job_discovery import JobDiscoveryError, search_multiple_roles
from app.services.job_sources.base import JobSourceError
from app.services.job_search import load_source_config, save_source_config, source_status
from app.services.portal_health import get_portal_health, check_portal_health
from app.services.job_detail_enricher import JobDetailFetchError, enrich_job_record
from app.services.job_storage import load_saved_jobs, save_jobs
from app.services.workflow_storage import load_job_triage, update_job_triage, record_event, load_events
from app.services.data_management import clear_cache_files, get_data_summary, reset_workspace_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Release the visible browser session cleanly when the local API stops."""
    start_scheduler()
    yield
    stop_scheduler()
    await close_browser_session()


class SavedSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    roles: list[str] = Field(min_length=1, max_length=5)
    country: str = Field(default="Sweden", max_length=80)
    city: str = Field(default="", max_length=100)
    work_mode: Literal["any", "remote", "hybrid", "on_site"] = "any"
    sources: list[str] = Field(default_factory=list, max_length=20)
    portal_ids: list[str] = Field(min_length=1, max_length=100)
    frequency: Literal["manual", "daily", "weekly"] = "manual"


class CvTailorRequest(BaseModel):
    job_description: str = Field(min_length=100, max_length=30000)
    template: Literal["classic", "modern", "compact", "sectioned"] = "sectioned"
    job_title: str = Field(default="", max_length=240)
    company: str = Field(default="", max_length=240)
    job_id: str = Field(default="", max_length=500)


class JobSourceConfigUpdate(BaseModel):
    greenhouse: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    lever: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    teamtailor: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    ashby: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    smartrecruiters: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    workable: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    recruitee: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    breezy: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    personio: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    workday: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


app = FastAPI(
    title="CareerMate API",
    description="Local-first job search and application assistant",
    version="3.8.0",
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


def _parse_published_date(value: str):
    from datetime import datetime, timezone, timedelta
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        pass
    lowered = raw.casefold()
    now = datetime.now(timezone.utc)
    if lowered in {"today", "posted today"}:
        return now
    if lowered in {"yesterday", "posted yesterday"}:
        return now - timedelta(days=1)
    match = re.search(r"(?:posted\s+)?(\d+)\s+days?\s+ago", lowered)
    if match:
        return now - timedelta(days=int(match.group(1)))
    return None


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


def _record_workflow_event(*args: Any, **kwargs: Any) -> None:
    """Keep workflow telemetry from breaking the core job/application action."""
    try:
        record_event(*args, **kwargs)
    except (RuntimeError, OSError, ValueError):
        logger.exception("Could not persist a workflow activity event")


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


@app.get("/api/data/summary")
def local_data_summary() -> dict[str, object]:
    """Return counts of local data without exposing its contents."""
    return get_data_summary(DATA_DIR)


@app.post("/api/data/clear-cache")
def clear_local_caches() -> dict[str, object]:
    """Clear derived caches while keeping the CV, jobs, profile and applications."""
    try:
        removed = clear_cache_files(DATA_DIR)
        return {"success": True, "removed_files": removed, "message": f"Cleared {removed} cache file(s).", **get_data_summary(DATA_DIR)}
    except OSError as exc:
        logger.exception("Could not clear CareerMate cache files")
        raise HTTPException(status_code=500, detail="Could not clear all cache files. Check file permissions and try again.") from exc


@app.post("/api/data/reset")
async def reset_local_workspace_data(request: LocalDataResetRequest) -> dict[str, object]:
    """Permanently remove user-generated files stored under data/ only."""
    if request.confirmation != "DELETE ALL LOCAL DATA":
        raise HTTPException(
            status_code=400,
            detail="Confirmation did not match. Type DELETE ALL LOCAL DATA to proceed.",
        )
    # Close the application browser first so transient form values are not left
    # in a live browser session during a workspace reset.
    try:
        await close_browser_session()
    except Exception as exc:
        logger.exception("Could not close the browser before workspace reset")
        raise HTTPException(status_code=500, detail="Could not close the browser session; no local data was reset. Close it and try again.") from exc
    try:
        removed = reset_workspace_data(DATA_DIR)
        return {
            "success": True,
            "removed_files": removed,
            "message": f"Workspace reset complete. Removed {removed} local data file(s).",
            **get_data_summary(DATA_DIR),
        }
    except OSError as exc:
        logger.exception("Could not reset CareerMate local workspace data")
        raise HTTPException(status_code=500, detail="Could not reset all local data. Check file permissions and inspect the workspace.") from exc


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


@app.get("/api/candidate/evidence")
def get_candidate_evidence() -> dict[str, object]:
    """Return locally stored professional claims and their verification state."""
    try:
        records = load_evidence()
        return {
            "success": True,
            "evidence": records,
            "verified_count": sum(1 for item in records if item["verified"]),
            "pending_count": sum(1 for item in records if not item["verified"]),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/candidate/evidence", status_code=201)
def create_candidate_evidence(request: CandidateEvidenceCreateRequest) -> dict[str, object]:
    """Create an unverified candidate claim. Verification always requires a separate action."""
    try:
        record = create_evidence(request.model_dump())
        return {"success": True, "evidence": record}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/candidate/evidence/{evidence_id}")
def update_candidate_evidence(evidence_id: str, request: CandidateEvidenceUpdateRequest) -> dict[str, object]:
    try:
        record = update_evidence(evidence_id, request.model_dump(exclude_unset=True))
        if record is None:
            raise HTTPException(status_code=404, detail="Candidate evidence was not found.")
        return {"success": True, "evidence": record}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/candidate/evidence/{evidence_id}")
def remove_candidate_evidence(evidence_id: str) -> dict[str, object]:
    try:
        if not delete_evidence(evidence_id):
            raise HTTPException(status_code=404, detail="Candidate evidence was not found.")
        return {"success": True, "message": "Candidate evidence deleted."}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/platforms")
def get_platform_directory() -> dict[str, object]:
    """Return the curated job-platform directory and integration capability labels."""
    items = list_platforms()
    return {
        "success": True,
        "total": len(items),
        "platforms": items,
        "integration_note": "Only sources labelled live have an automatic connector in this build. External platforms open their own search pages."
    }


@app.post("/api/cv/tailor")
def tailor_cv_for_job(request: CvTailorRequest) -> dict[str, object]:
    """Generate an evidence-grounded DOCX CV and transparent ATS heuristic score."""
    if not PROFILE_PATH.exists():
        raise HTTPException(status_code=400, detail="Upload and analyse your base CV before tailoring it.")
    try:
        profile = CandidateProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))
        result = create_tailored_cv(
            profile,
            request.job_description,
            request.template,
            job_title=request.job_title,
            company=request.company,
            job_id=request.job_id,
        )
        result.pop("download_path", None)
        result["download_url"] = f"/api/cv/tailored/{result['filename']}"
        return {"success": True, **result}
    except (ValueError, AIProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("CV tailoring failed")
        raise HTTPException(status_code=500, detail="Could not generate the tailored CV. Check the AI provider and try again.") from exc


@app.get("/api/cv/tailored/{filename}")
def download_tailored_cv(filename: str):
    """Download a generated DOCX from the local tailored-CV workspace."""
    safe_name = Path(filename).name
    path = OUTPUT_DIR / safe_name
    if safe_name != filename or not path.is_file() or path.suffix.lower() != ".docx":
        raise HTTPException(status_code=404, detail="Tailored CV not found.")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=safe_name)


@app.get("/api/cv/tailored")
def get_tailored_cv_versions(limit: int = Query(default=50, ge=1, le=200)):
    return {"success": True, "versions": list_tailored_versions(limit)}


@app.get("/api/cv/tailored/{filename}/preview")
def preview_tailored_cv_pdf(filename: str):
    try:
        path = export_tailored_pdf(filename)
        return FileResponse(path, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{path.name}"'})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Tailored CV PDF preview failed for %s", filename)
        raise HTTPException(status_code=500, detail=f"PDF preview generation failed: {type(exc).__name__}. Check the backend log for details.") from exc


@app.get("/api/cv/tailored/{filename}/pdf")
def download_tailored_cv_pdf(filename: str):
    try:
        path = export_tailored_pdf(filename)
        return FileResponse(path, media_type="application/pdf", filename=path.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Tailored CV PDF download failed for %s", filename)
        raise HTTPException(status_code=500, detail=f"PDF export failed: {type(exc).__name__}. Check the backend log for details.") from exc


@app.get("/api/alerts")
def get_job_alerts(limit: int = Query(default=100, ge=1, le=500)):
    items = list_alert_history(limit)
    return {"success": True, "alerts": items, "unread": sum(1 for item in items if not item.get("read"))}


@app.post("/api/alerts/{alert_id}/read")
def mark_job_alert_read(alert_id: str):
    if not mark_alert_read(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {"success": True}


@app.get("/api/searches")
def get_saved_searches():
    return {"success": True, "searches": list_searches()}


@app.post("/api/searches")
def create_saved_search(request: SavedSearchRequest):
    item = save_search(request.model_dump())
    from app.services.alert_scheduler import refresh_schedules
    refresh_schedules()
    return {"success": True, "search": item}


@app.delete("/api/searches/{search_id}")
def remove_saved_search(search_id: str):
    if not delete_search(search_id):
        raise HTTPException(status_code=404, detail="Saved search not found.")
    from app.services.alert_scheduler import refresh_schedules
    refresh_schedules()
    return {"success": True}


@app.post("/api/searches/{search_id}/check-alerts")
def check_saved_search_alerts(search_id: str):
    item = next((x for x in list_searches() if x.get("id") == search_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Saved search not found.")
    portal_ids = item.get("portal_ids")
    if not isinstance(portal_ids, list) or not any(str(value).strip() for value in portal_ids):
        raise HTTPException(
            status_code=409,
            detail="This saved search predates company-level portal selection. Create a new search and select the employer portals to monitor.",
        )
    try:
        result = search_multiple_roles(roles=item["roles"], country=item.get("country","Sweden"),
            city=item.get("city",""), work_mode=item.get("work_mode","any"),
            sources=item.get("sources") or None, portal_ids=portal_ids, limit=40, offset=0)
        jobs = [x.model_dump() for x in result.get("all_jobs", result.get("jobs", []))]
        delta = scan_alerts(search_id, jobs)
        record_alerts(search_id, item.get("name","Saved search"), delta["new_jobs"])
        return {"success": True, **delta}
    except (JobDiscoveryError, JobSourceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/jobs/search")
def search_job_listings(
    roles: list[str] = Query(default=[]),
    query: str | None = Query(default=None, min_length=2, max_length=100),
    country: str = Query(default="Sweden", max_length=80),
    city: str = Query(default="", max_length=100),
    location: str = Query(default="", max_length=100),
    work_mode: Literal["any", "remote", "hybrid", "on_site"] = Query(default="any"),
    sources: list[str] | None = Query(default=None),
    portal_ids: list[str] | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=40),
    offset: int = Query(default=0, ge=0, le=50000),
    min_salary: int | None = Query(default=None, ge=0),
    max_salary: int | None = Query(default=None, ge=0),
    salary_currency: str = Query(default="", max_length=5),
    posted_within_days: int | None = Query(default=None, ge=1, le=365),
    excluded_companies: list[str] = Query(default=[]),
    refresh_portals: bool = Query(default=False),
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
            portal_ids=portal_ids,
            offset=offset,
            force_portal_refresh=refresh_portals,
        )
        jobs = result["jobs"]
        page_job_payload = [job.model_dump() for job in jobs]  # type: ignore[union-attr]
        # The employer-board connectors fetch complete published inventories.
        # Keep a page-sized slice for backwards-compatible API consumers, but
        # also return the complete eligible, de-duplicated inventory to Explore.
        # Explore sorts, filters and paginates this full set locally; otherwise a
        # page of 20 could hide matches which were counted in portal coverage.
        all_jobs = result.get("all_jobs", jobs)
        all_job_payload = [job.model_dump() for job in all_jobs]  # type: ignore[union-attr]
        pre_advanced_filter_count = len(all_job_payload)
        from datetime import datetime, timezone, timedelta
        excluded = {x.casefold().strip() for x in excluded_companies if x.strip()}
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_within_days) if posted_within_days else None

        def apply_optional_search_filters(items: list[dict[str, object]]) -> list[dict[str, object]]:
            eligible: list[dict[str, object]] = []
            for item in items:
                item.update(extract_salary(str(item.get("description", ""))))
                company = str(item.get("company", "")).casefold()
                if any(blocked in company for blocked in excluded):
                    continue
                if salary_currency and item.get("salary_currency") and str(item["salary_currency"]).casefold() != salary_currency.casefold():
                    continue
                if min_salary is not None and (item.get("salary_min") is None or int(item["salary_min"]) < min_salary):
                    continue
                if max_salary is not None and (item.get("salary_max") is None or int(item["salary_max"]) > max_salary):
                    continue
                if cutoff:
                    published = _parse_published_date(str(item.get("published_at", "")))
                    if published is None or published < cutoff:
                        continue
                eligible.append(item)
            return eligible

        # Apply the same advanced filters to the complete inventory before it is
        # persisted, so hidden salary/freshness exclusions do not enter the Inbox.
        all_job_payload = apply_optional_search_filters(all_job_payload)
        page_job_payload = apply_optional_search_filters(page_job_payload)
        # Coverage's returned count reflects the complete inventory that will
        # be available in Explore after advanced salary/freshness/company filters.
        portal_coverage = result.get("portal_results", [])
        if isinstance(portal_coverage, list):
            for portal_item in portal_coverage:
                if isinstance(portal_item, dict):
                    portal_id = str(portal_item.get("portal_id", ""))
                    portal_item["returned_count"] = sum(
                        1 for item in all_job_payload if str(item.get("portal_id", "")) == portal_id
                    )
        saved_total = save_jobs(all_job_payload)
        # Reuse a previously fetched full description when the same job appears
        # again in a later search and the provider only returns a short teaser.
        saved_by_id = {str(item.get("id", "")): item for item in load_saved_jobs()}
        response_jobs: list[dict[str, object]] = []
        for item in page_job_payload:
            saved = saved_by_id.get(str(item.get("id", "")), {})
            if saved.get("description_source") == "original_listing" and len(str(saved.get("description", ""))) > len(str(item.get("description", ""))):
                response_jobs.append({**item, **{
                    key: saved[key] for key in (
                        "description", "description_source", "description_fetch_status",
                        "description_fetched_at", "description_fetch_message",
                    ) if key in saved
                }})
            else:
                response_jobs.append(item)

        normalized_jobs = response_jobs
        # Apply the same saved-description fallback to the complete inventory,
        # not only the compatibility page. This keeps CV tailoring consistent
        # no matter which local page or sort order the user opens.
        response_matching_jobs: list[dict[str, object]] = []
        for item in all_job_payload:
            saved = saved_by_id.get(str(item.get("id", "")), {})
            if saved.get("description_source") == "original_listing" and len(str(saved.get("description", ""))) > len(str(item.get("description", ""))):
                response_matching_jobs.append({**item, **{
                    key: saved[key] for key in (
                        "description", "description_source", "description_fetch_status",
                        "description_fetched_at", "description_fetch_message",
                    ) if key in saved
                }})
            else:
                response_matching_jobs.append(item)

        _record_workflow_event(
            "discovery_scan",
            "Job discovery completed",
            f"Discovered {len(all_job_payload)} unique eligible listings across the selected employer boards and returned the full filtered inventory to Explore.",
            entity_type="search",
            metadata={
                "roles": role_values,
                "country": country,
                "city": effective_city,
                "sources": sources or [],
                "portal_ids": portal_ids or [],
                "returned": len(normalized_jobs),
                "saved_total": saved_total,
            },
        )
        return {
            "success": True,
            **{key: value for key, value in result.items() if key not in {"jobs", "all_jobs"}},
            "saved_total": saved_total,
            "discovered_this_search": len(all_job_payload),
            "matching_jobs": response_matching_jobs,
            "matching_jobs_count": len(response_matching_jobs),
            "advanced_filtered_out": max(0, pre_advanced_filter_count - len(all_job_payload)),
            "jobs": normalized_jobs,
            "returned": len(normalized_jobs),
            "local_filters": {"min_salary": min_salary, "max_salary": max_salary, "salary_currency": salary_currency, "posted_within_days": posted_within_days, "excluded_companies": excluded_companies},
        }
    except JobDiscoveryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except JobSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Could not save job search results")
        raise HTTPException(status_code=500, detail="Could not save job listings locally.") from exc


@app.get("/api/jobs/source-config")
def get_job_source_config() -> dict[str, object]:
    """Return editable per-employer board identifiers and safe API-key variable names."""
    try:
        return {"success": True, "config": load_source_config(), "sources": source_status()}
    except JobSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/jobs/source-config")
def update_job_source_config(request: JobSourceConfigUpdate) -> dict[str, object]:
    """Save job-source board configuration locally; API key values never belong here."""
    try:
        config = save_source_config(request.model_dump())
        return {"success": True, "config": config, "sources": source_status(), "message": "Job platform configuration saved locally."}
    except JobSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Could not save job platform configuration")
        raise HTTPException(status_code=500, detail="Could not save platform settings to data/sources.json.") from exc


@app.get("/api/jobs/portal-health")
def get_employer_portal_health() -> dict[str, object]:
    """Return configured employer portals and their latest health observations."""
    try:
        return get_portal_health()
    except JobSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Could not load employer portal health data.") from exc


@app.post("/api/jobs/portal-health/check")
def run_employer_portal_health_check() -> dict[str, object]:
    """Check read-only public ATS endpoints for configured employer portals."""
    try:
        return check_portal_health()
    except JobSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("Could not persist employer portal health results")
        raise HTTPException(status_code=500, detail="Could not save employer portal health results locally.") from exc


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


@app.get("/api/workflow/inbox")
def get_workflow_inbox(response: Response) -> dict[str, object]:
    """Return discovered jobs that have not yet been promoted into the pipeline."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        jobs = load_saved_jobs()
        applications = load_applications()
        triage = load_job_triage()
    except RuntimeError as exc:
        logger.exception("Could not load workflow inbox")
        raise HTTPException(status_code=500, detail="Could not load the local job inbox.") from exc

    tracked_job_ids = {str(item.get("job_id", "")) for item in applications}
    items: list[dict[str, object]] = []
    counts = {"new": 0, "reviewing": 0, "shortlisted": 0, "skipped": 0}
    for job in jobs:
        job_id = str(job.get("id", ""))
        if not job_id or job_id in tracked_job_ids:
            continue
        triage_record = triage.get(job_id) or {
            "job_id": job_id,
            "stage": "new",
            "notes": "",
            "created_at": "",
            "updated_at": "",
        }
        stage = str(triage_record.get("stage", "new"))
        if stage not in counts:
            stage = "new"
            triage_record["stage"] = stage
        counts[stage] += 1
        items.append({"job": job, "triage": triage_record})

    items.sort(
        key=lambda item: str(item["job"].get("published_at", "") or ""),
        reverse=True,
    )
    return {"success": True, "total": len(items), "counts": counts, "items": items}


@app.put("/api/workflow/jobs/{job_id}/triage")
def set_workflow_job_triage(job_id: str, request: JobTriageUpdateRequest) -> dict[str, object]:
    """Update a discovered job's triage stage without changing the job record."""
    try:
        exists = any(str(item.get("id", "")) == job_id for item in load_saved_jobs())
        if not exists:
            raise HTTPException(status_code=404, detail="Job not found in the local discovery store.")
        previous = load_job_triage().get(job_id, {"stage": "new", "notes": ""})
        triage_record = update_job_triage(job_id, request.stage, request.notes)
        if previous.get("stage") != triage_record.get("stage") or previous.get("notes", "") != triage_record.get("notes", ""):
            _record_workflow_event(
                "job_triage_updated",
                f"Job moved to {request.stage.replace('_', ' ')}",
                str((next((job.get("title", "Job") for job in load_saved_jobs() if str(job.get("id", "")) == job_id), "Job"))),
                entity_type="job",
                entity_id=job_id,
                metadata={"from_stage": previous.get("stage", "new"), "to_stage": request.stage},
            )
        return {"success": True, "triage": triage_record}
    except HTTPException:
        raise
    except (RuntimeError, ValueError) as exc:
        logger.exception("Could not update job triage")
        raise HTTPException(status_code=500, detail="Could not update the job's triage state.") from exc


@app.get("/api/workflow/activity")
def get_workflow_activity(response: Response, limit: int = Query(default=30, ge=1, le=200)) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    try:
        events = load_events(limit)
    except RuntimeError as exc:
        logger.exception("Could not load workflow activity")
        raise HTTPException(status_code=500, detail="Could not load workflow activity.") from exc
    return {"success": True, "events": events}


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
        source_url = str(job.get("source_url") or job_url or "")
        if not job_url.startswith(("https://", "http://")):
            job_url = ""
        if not source_url.startswith(("https://", "http://")):
            source_url = ""
        record = ApplicationRecord(
            id=f"application:{uuid4().hex}",
            job_id=request.job_id,
            company=str(job.get("company", ""))[:300],
            title=str(job.get("title", ""))[:500],
            location=str(job.get("location", ""))[:300],
            source=str(job.get("source", ""))[:100],
            job_url=job_url[:2000],
            source_url=source_url[:2000],
            job_description=str(job.get("description", ""))[:30000],
            job_description_source=str(job.get("description_source", "search_result")),
            job_description_fetched_at=str(job.get("description_fetched_at", "")),
            job_description_fetch_status=str(job.get("description_fetch_status", "not_attempted")),
            status="saved",
            notes=request.notes,
            created_at=now,
            updated_at=now,
        ).model_dump()
        saved_record, created = create_application(record)
        if created:
            _record_workflow_event(
                "application_created",
                "Job added to pipeline",
                f"{saved_record.get('title', 'Role')} · {saved_record.get('company', 'Company not listed')}",
                entity_type="application",
                entity_id=str(saved_record["id"]),
                metadata={"job_id": request.job_id, "status": saved_record.get("status", "saved")},
            )
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
        existing_application = next((item for item in load_applications() if item["id"] == application_id), None)
        existing_status = existing_application.get("status") if existing_application else None
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
    previous_status = existing_status if "existing_status" in locals() else None
    if "status" in updates and previous_status != saved_record.get("status"):
        _record_workflow_event(
            "application_stage_changed",
            f"Application moved to {str(saved_record.get('status', '')).replace('_', ' ')}",
            f"{saved_record.get('title', 'Role')} · {saved_record.get('company', 'Company not listed')}",
            entity_type="application",
            entity_id=application_id,
            metadata={"from_status": previous_status, "to_status": saved_record.get("status")},
        )
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
    application = _refresh_application_description(application)
    if application.job_description_source != "original_listing" and len(application.job_description.strip()) < 500:
        raise HTTPException(
            status_code=409,
            detail=(
                "CareerMate only has a short search snippet for this role, so it cannot reliably tailor a complete cover letter yet. "
                "Use ‘Fetch full details’ in the application workspace and retry. If the public site blocks retrieval, review the advert manually before drafting."
            ),
        )
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
    application = _refresh_application_description(application)
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


@app.get("/api/browser/diagnostics")
async def browser_diagnostics() -> dict[str, object]:
    """Check Playwright and Chromium availability without opening a browser."""
    return await get_browser_diagnostics()


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
    """Fill only reviewed field values; this endpoint never submits the application."""
    try:
        fields = [item.model_dump() for item in request.fields]
        return await fill_reviewed_fields(application_id, fields, request.expected_url)
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/applications/{application_id}/browser/advance")
async def advance_application_browser_step(
    application_id: str,
    request: BrowserNavigationRequest,
) -> dict[str, object]:
    """Navigate one safe public Apply or Continue step without submitting."""
    try:
        return await advance_application_step(application_id, request.intent)
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/applications/{application_id}/browser/select-page")
async def select_application_browser_page(
    application_id: str,
    request: BrowserPageSelectRequest,
) -> dict[str, object]:
    """Select which open Chromium tab CareerMate should inspect and fill."""
    try:
        return await select_browser_page(application_id, request.page_index)
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/applications/{application_id}/browser/suggest")
async def suggest_application_browser_answers(
    application_id: str,
    request: BrowserSuggestionRequest,
) -> dict[str, object]:
    """Draft answers for review using the selected AI provider; nothing is filled automatically."""
    application, profile = _load_draft_inputs(application_id)
    try:
        return await suggest_browser_answers(application_id, request.field_ids, application, profile, request.expected_url)
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/applications/{application_id}/browser/submit")
async def submit_application_browser_form(
    application_id: str,
    request: BrowserSubmitRequest,
) -> dict[str, object]:
    """Click a final submit control only after the user explicitly approves submission."""
    if not request.confirm_submission:
        raise HTTPException(status_code=409, detail="Final submission was not approved. Review the employer form and confirm explicitly before submitting.")
    try:
        result = await submit_reviewed_application(application_id, request.confirm_submission, request.expected_url)
        if result.get("confirmation_detected"):
            saved = update_application(application_id, {"status": "applied", "applied_at": utc_now(), **({"submitted_details": [item.model_dump() for item in request.submitted_details]} if request.submitted_details else {})})
            if saved is not None:
                result["application"] = saved
        return result
    except BrowserAssistanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/browser/session")
async def end_browser_session() -> dict[str, object]:
    return await close_browser_session()


def _try_enrich_job(job: dict[str, object], *, force: bool = False) -> dict[str, object]:
    """Best-effort public-page enrichment; keep source data if enrichment fails."""
    result = dict(job)
    description = str(result.get("description", "")).strip()
    if not force and (result.get("description_source") == "original_listing" or len(description) >= 1800):
        result.setdefault("description_source", "search_result")
        result.setdefault("description_fetch_status", "not_attempted")
        return result
    try:
        return enrich_job_record(result, force=force)
    except JobDetailFetchError as exc:
        result["description_source"] = str(result.get("description_source") or "search_result")
        result["description_fetch_status"] = "failed"
        result["description_fetch_message"] = str(exc)[:300]
        return result


@app.post("/api/jobs/enrich")
def enrich_saved_job_details(request: JobEnrichmentRequest) -> dict[str, object]:
    """Fetch fuller text from a selected job's public original listing."""
    try:
        saved_jobs = load_saved_jobs()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Could not load saved job listings.") from exc
    job = next((item for item in saved_jobs if str(item.get("id", "")) == request.job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found in local saved jobs. Search for it again first.")

    if request.manual_description is not None:
        # User-pasted text is an intentional fallback for public ATS pages whose
        # readable content is unavailable to the safe static/browser fetcher.
        manual_text = "\n".join(" ".join(line.split()) for line in request.manual_description.splitlines()).strip()
        if len(manual_text) < 300:
            return {
                "success": False,
                "message": "Paste at least 300 characters from the original advert so CareerMate has enough context to analyse.",
                "job": job,
            }
        manual_job = dict(job)
        manual_job.update({
            "description": manual_text[:30000],
            "description_source": "original_listing",
            "description_fetch_status": "success",
            "description_fetched_at": "",
            "description_fetch_message": (
                "Manually pasted advert text saved locally; CareerMate has not independently verified it against the source page."
            ),
        })
        try:
            save_jobs([manual_job])
        except RuntimeError as exc:
            logger.exception("Could not save manually supplied advert text")
            raise HTTPException(status_code=500, detail="Could not save the pasted advert text locally.") from exc
        return {
            "success": True,
            "message": "Advert text saved locally. CareerMate will reanalyse the pasted content; verify it matches the employer page.",
            "job": manual_job,
        }

    enriched = _try_enrich_job(job, force=request.force_refresh)
    if enriched.get("description_fetch_status") != "success":
        message = str(enriched.get("description_fetch_message") or "CareerMate could not obtain a fuller description from the public listing.")
        # A failed refresh returns useful current data and a warning; this is not
        # a server error because the existing snippet remains usable.
        return {"success": False, "message": message, "job": enriched}
    try:
        save_jobs([enriched])
    except RuntimeError as exc:
        logger.exception("Could not persist enriched job description")
        raise HTTPException(status_code=500, detail="Fetched the description but could not save it locally.") from exc
    return {"success": True, "message": "Fuller description saved from the public original listing.", "job": enriched}


def _refresh_application_description(
    application: ApplicationRecord,
    *,
    force: bool = False,
) -> ApplicationRecord:
    """Try enriching an older short application snapshot before generating drafts."""
    if application.job_description_source == "original_listing" and len(application.job_description) >= 1800:
        return application
    if not force and application.job_description_fetch_status == "failed":
        return application
    source_url = application.source_url or application.job_url
    if not source_url:
        return application
    job_for_enrichment: dict[str, object] = {
        "id": application.job_id,
        "source": application.source,
        "source_id": application.job_id,
        "title": application.title,
        "company": application.company,
        "location": application.location,
        "description": application.job_description,
        "source_url": source_url,
        "apply_url": application.job_url or source_url,
        "description_source": application.job_description_source,
        "description_fetch_status": application.job_description_fetch_status,
    }
    enriched = _try_enrich_job(job_for_enrichment, force=force)
    updates: dict[str, object] = {
        "job_description_fetch_status": str(enriched.get("description_fetch_status", "not_attempted")),
        "job_description_fetch_message": str(enriched.get("description_fetch_message", ""))[:500],
    }
    if enriched.get("description_source") == "original_listing":
        updates.update({
            "job_description": str(enriched.get("description", ""))[:30000],
            "job_description_source": "original_listing",
            "job_description_fetched_at": str(enriched.get("description_fetched_at", "")),
            "job_description_fetch_status": "success",
            "job_description_fetch_message": "Full text retrieved from the public original listing.",
        })
    elif enriched.get("description_fetch_status") == "failed":
        logger.info("Could not enrich application description (%s): %s", application.job_id, updates["job_description_fetch_message"])
    saved = update_application(application.id, updates)
    if saved:
        return ApplicationRecord.model_validate(saved)
    return application


@app.post("/api/applications/{application_id}/enrich-description")
def enrich_application_description(application_id: str) -> dict[str, object]:
    """Refresh the public listing description for an application record."""
    try:
        records = load_applications()
        record = next((item for item in records if item.get("id") == application_id), None)
        if record is None:
            raise HTTPException(status_code=404, detail="Application record not found.")
        application = ApplicationRecord.model_validate(record)
        enriched = _refresh_application_description(application, force=True)
        success = enriched.job_description_source == "original_listing"
        return {
            "success": success,
            "message": enriched.job_description_fetch_message or (
                "Full job description refreshed." if success else "The listing did not provide a fuller description."
            ),
            "application": enriched.model_dump(),
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Could not refresh the application description.") from exc


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

    # Job-search adapters often return only a teaser. Fetch the public listing
    # for selected jobs before scoring so a match is based on the actual requirements.
    if selected_jobs:
        with ThreadPoolExecutor(max_workers=min(4, len(selected_jobs)), thread_name_prefix="careermate-job-page") as executor:
            selected_jobs = list(executor.map(_try_enrich_job, selected_jobs))
        enriched_jobs = [job for job in selected_jobs if job.get("description_source") == "original_listing"]
        if enriched_jobs:
            try:
                save_jobs(enriched_jobs)
            except RuntimeError:
                logger.warning("Could not persist one or more enriched job descriptions")

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
        "method": f"{provider}_llm_evidence_weighted_v6",
        "provider": provider,
        "model": model,
        "concurrency": min(4, len(selected_jobs)) if provider != "ollama" else 1,
        "jobs": results,
    }
