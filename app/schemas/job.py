from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NormalizedJob(BaseModel):
    source: str
    source_job_id: str
    company_name: str
    title: str
    normalized_title: str | None = None
    description: str | None = None
    description_html: str | None = None
    location: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    country_code: str | None = None
    remote_type: str = "unknown"
    employment_type: str | None = None
    seniority: str | None = None
    department: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_raw: str | None = None
    posted_at: datetime | None = None
    updated_at: datetime | None = None
    apply_url: str | None = None
    source_url: str | None = None
    primary_category: str | None = None
    secondary_categories: list[str] = []
    skills: list[str] = []
    source_metadata: dict | list | None = None
    raw_data_path: str | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_job_id: str
    company_name: str
    title: str
    normalized_title: str | None
    description: str | None
    location: str | None
    remote_type: str
    employment_type: str | None
    country_code: str | None = None
    primary_category: str | None
    secondary_categories: list[str]
    skills: list
    apply_url: str | None
    source_url: str | None
    posted_at: datetime | None
    status: str
