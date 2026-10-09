from pydantic import BaseModel, ConfigDict, Field


class CandidatePersonal(BaseModel):
    """Explicit, predictable contact/profile fields."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class Experience(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    job_title: str = ""
    company: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: list[str] = Field(default_factory=list)


class Education(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    degree: str = ""
    institution: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""


class CandidateProfile(BaseModel):
    """Structured candidate data used by the rest of CareerMate."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    personal: CandidatePersonal = Field(default_factory=CandidatePersonal)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
