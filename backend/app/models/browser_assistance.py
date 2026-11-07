"""Bounded request models for the reviewed browser-assistance workflow."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.application import ApplicationAnswer


class BrowserFieldValue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field_id: str = Field(pattern=r"^cm-field-[0-9]{1,4}$", max_length=32)
    value: str = Field(max_length=12000)


class BrowserFillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[BrowserFieldValue] = Field(min_length=1, max_length=80)
    expected_url: str | None = Field(default=None, max_length=3000)


class BrowserNavigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["apply", "continue"]


class BrowserPageSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0, le=30)


class BrowserSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_ids: list[str] = Field(min_length=1, max_length=8)
    expected_url: str | None = Field(default=None, max_length=3000)

    @classmethod
    def validate_field_ids(cls, value: list[str]) -> list[str]:
        if any(not isinstance(item, str) or not __import__("re").fullmatch(r"cm-field-[0-9]{1,4}", item) for item in value):
            raise ValueError("Only scanned CareerMate form fields can be selected.")
        return value

    # Pydantic v2 field validator is declared separately to keep the public
    # request schema explicit.
    _valid_ids = field_validator("field_ids")(validate_field_ids)


class BrowserSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_submission: bool = False
    expected_url: str | None = Field(default=None, max_length=3000)
    submitted_details: list[ApplicationAnswer] = Field(default_factory=list, max_length=50)
