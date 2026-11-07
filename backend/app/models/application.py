"""Validated local application and employer-question records.

These models intentionally stay independent of any particular job board. They
also accept older records with optional fields missing so existing local JSON
workspaces remain readable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ApplicationStatus = Literal["saved", "preparing", "applied", "interview", "offer", "rejected", "withdrawn"]


class ApplicationAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(default="", max_length=12000)
    updated_at: str = ""


class ApplicationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    job_id: str = Field(min_length=1, max_length=500)
    notes: str = Field(default="", max_length=12000)


class ApplicationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: ApplicationStatus | None = None
    notes: str | None = Field(default=None, max_length=12000)
    follow_up_date: str | None = Field(default=None, max_length=40)
    cover_letter: str | None = Field(default=None, max_length=30000)
    answers: list[ApplicationAnswer] | None = Field(default=None, max_length=50)
    submitted_details: list[ApplicationAnswer] | None = Field(default=None, max_length=50)


class DraftAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=5, max_length=4000)


class ApplicationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=500)
    job_id: str = Field(min_length=1, max_length=500)
    company: str = Field(default="", max_length=300)
    title: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=300)
    source: str = Field(default="", max_length=100)
    job_url: str = Field(default="", max_length=2000)
    source_url: str = Field(default="", max_length=2000)
    job_description: str = Field(default="", max_length=30000)
    job_description_source: str = "search_result"
    job_description_fetched_at: str = ""
    job_description_fetch_status: str = "not_attempted"
    job_description_fetch_message: str = Field(default="", max_length=2000)
    status: ApplicationStatus = "saved"
    notes: str = Field(default="", max_length=12000)
    follow_up_date: str = ""
    cover_letter: str = Field(default="", max_length=30000)
    answers: list[ApplicationAnswer] = Field(default_factory=list, max_length=50)
    submitted_details: list[ApplicationAnswer] = Field(default_factory=list, max_length=50)
    created_at: str = ""
    updated_at: str = ""
    applied_at: str = ""

    @field_validator("job_url", "source_url")
    @classmethod
    def normalize_urls(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("https://", "http://")):
            return ""
        return value
