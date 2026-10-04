from bs4 import BeautifulSoup

from app.normalization.salaries import parse_salary
from app.schemas.job import NormalizedJob


def clean_html(value: str | None) -> str | None:
    if not value:
        return None
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def enrich(job: NormalizedJob) -> NormalizedJob:
    if job.description_html and not job.description:
        job.description = clean_html(job.description_html)
    if job.salary_raw and job.salary_min is None and job.salary_max is None:
        parsed = parse_salary(job.salary_raw)
        for field in ("salary_min", "salary_max", "salary_currency", "salary_period"):
            if getattr(job, field) is None:
                setattr(job, field, parsed[field])
    job.normalized_title = " ".join((job.title or "").lower().split()) or None
    return job
