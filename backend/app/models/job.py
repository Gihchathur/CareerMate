from typing import Literal

from pydantic import BaseModel, Field


WorkMode = Literal["remote", "hybrid", "on_site", "unknown"]


class JobPosting(BaseModel):
    id: str
    source: str
    source_id: str
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
    search_roles: list[str] = Field(default_factory=list)
    description_source: Literal["search_result", "original_listing"] = "search_result"
    description_fetch_status: Literal["not_attempted", "success", "failed"] = "not_attempted"
    description_fetched_at: str = ""
    description_fetch_message: str = ""


class JobEnrichmentRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=300)
    force_refresh: bool = False
