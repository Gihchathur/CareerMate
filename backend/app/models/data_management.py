"""Explicit confirmation for destructive local workspace operations."""
from pydantic import BaseModel, ConfigDict, Field


class LocalDataResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    confirmation: str = Field(min_length=1, max_length=100)
