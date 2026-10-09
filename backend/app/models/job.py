
from pydantic import BaseModel


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
