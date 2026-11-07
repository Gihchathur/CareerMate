from typing import Literal

from pydantic import BaseModel, Field


WorkMode = Literal["remote", "hybrid", "on_site", "unknown"]


class JobPosting(BaseModel):
    id: str
    source: str
    source_id: str
    # Stable company-board identity keeps jobs attributable to the exact portal.
    portal_id: str = ""
    portal_name: str = ""
    source_fetched_at: str = ""
    title: str
    company: str
    location: str
    description: str
    published_at: str
    source_url: str
    apply_url: str
    # Optional metadata keeps older jobs.json records readable.
    city: str = ""
    country: str = ""
    work_mode: WorkMode = "unknown"
    department: str = ""
    team: str = ""
    employment_type: str = ""
    # Structured role metadata is safe to use for matching; free-text descriptions are not.
    role_metadata: list[str] = Field(default_factory=list)
    search_roles: list[str] = Field(default_factory=list)
    description_source: Literal["search_result", "original_listing"] = "search_result"
    description_fetch_status: Literal["not_attempted", "success", "failed"] = "not_attempted"
    description_fetched_at: str = ""
    description_fetch_message: str = ""


class JobEnrichmentRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=300)
    force_refresh: bool = False
    # Optional local fallback for ATS pages that block or require JavaScript rendering.
    manual_description: str | None = Field(default=None, max_length=30000)
