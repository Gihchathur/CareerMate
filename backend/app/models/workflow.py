"""Validated models for the guided job-search workflow."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TriageStage = Literal["new", "reviewing", "shortlisted", "skipped"]


class JobTriageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: TriageStage
    notes: str | None = Field(default=None, max_length=4000)
