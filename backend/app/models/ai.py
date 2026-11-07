"""Credential-safe AI settings request models."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

AIProvider = Literal["ollama", "openai", "openai_compatible"]


class AISettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: AIProvider
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default="", max_length=1000)
    confirm_cloud_data_sharing: bool = False


class AIProviderTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: AIProvider
    model: str = Field(min_length=1, max_length=160)
    base_url: str = Field(default="", max_length=1000)
