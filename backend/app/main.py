import logging
import os
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.models.candidate import CandidateProfile
from app.services.cv_analyzer import CVAnalyzerError, analyze_cv
from app.services.cv_parser import CVParserError, extract_cv_text
from app.services.job_matcher import score_job
from app.services.job_discovery import JobDiscoveryError, search_multiple_roles
from app.services.job_sources.base import JobSourceError
from app.services.job_search import source_status
from app.services.job_storage import load_saved_jobs, save_jobs

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CareerMate API",
    description="Local-first job search and application assistant",
    version="0.2.0",
)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
CV_DIR = DATA_DIR / "cv"
JOBS_DIR = DATA_DIR / "jobs"
PROFILE_PATH = CV_DIR / "profile.json"
EXTRACTED_TEXT_PATH = CV_DIR / "extracted_text.txt"

CV_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

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
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


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


@app.get("/api/jobs/matches")
def get_job_matches(
    limit: int = Query(default=5, ge=1, le=20),
    job_ids: list[str] | None = Query(default=None),
) -> dict[str, object]:
    """Analyze at most `limit` saved jobs to bound local-model latency."""
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
    for job in selected_jobs:
        match = score_job(job, profile.model_dump())
        results.append({**job, **match})

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
        "method": "local_llm_evidence_weighted_v2",
        "jobs": results,
    }
