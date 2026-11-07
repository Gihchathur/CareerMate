"""Candidate evidence records used to ground job matching and generated documents."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceCategory = Literal[
    "skill", "experience", "project", "achievement", "education",
    "certification", "language", "metric", "other",
]
EvidenceSource = Literal["cv", "experience", "project", "certification", "reference", "manual"]


class CandidateEvidenceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim: str = Field(min_length=3, max_length=1200)
    category: EvidenceCategory = "skill"
    source_type: EvidenceSource = "manual"
    source_reference: str = Field(default="", max_length=500)
    supporting_detail: str = Field(default="", max_length=4000)


class CandidateEvidenceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim: str | None = Field(default=None, min_length=3, max_length=1200)
    category: EvidenceCategory | None = None
    source_type: EvidenceSource | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    supporting_detail: str | None = Field(default=None, max_length=4000)
    verified: bool | None = None


class CandidateEvidenceRecord(CandidateEvidenceCreateRequest):
    id: str = Field(min_length=1, max_length=64)
    verified: bool = False
    created_at: str
    updated_at: str
