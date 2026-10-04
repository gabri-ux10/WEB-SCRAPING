from datetime import datetime
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Job, Location
from app.database.session import SessionLocal

router = APIRouter(prefix="/jobs", tags=["jobs"])
_region_config = Path(__file__).resolve().parents[3] / "config" / "regions.yml"
REGION_COUNTRIES = yaml.safe_load(_region_config.read_text(encoding="utf-8")).get("regions", {})


async def db_session():
    async with SessionLocal() as session:
        yield session


@router.get("")
async def list_jobs(
    q: str | None = None,
    country: str | None = None,
    region: str | None = None,
    city: str | None = None,
    remote_type: str | None = None,
    employment_type: str | None = None,
    category: str | None = None,
    skill: str | None = None,
    company: str | None = None,
    source: str | None = None,
    posted_after: datetime | None = None,
    posted_before: datetime | None = None,
    salary_min: float | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(db_session),
):
    stmt = (
        select(Job)
        .options(
            selectinload(Job.source), selectinload(Job.skills), selectinload(Job.location_record)
        )
        .where(Job.status == "open")
    )
    if q:
        stmt = stmt.where(
            or_(
                Job.title.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
                Job.company_name.ilike(f"%{q}%"),
            )
        )
    if country:
        stmt = stmt.where(Job.location_record.has(Location.country_code == country.upper()))
    if city:
        stmt = stmt.where(Job.location_record.has(Location.city.ilike(f"%{city}%")))
    if region:
        countries = REGION_COUNTRIES.get(region.lower(), {}).get("countries", [])
        if countries:
            stmt = stmt.where(Job.location_record.has(Location.country_code.in_(countries)))
        elif region.lower() != "global":
            stmt = stmt.where(Job.company.has(region=region))
    if remote_type:
        stmt = stmt.where(Job.remote_type == remote_type.lower())
    if employment_type:
        stmt = stmt.where(Job.employment_type.ilike(f"%{employment_type}%"))
    if category:
        stmt = stmt.where(
            or_(
                Job.primary_category.ilike(f"%{category}%"),
                Job.secondary_categories.cast(str).ilike(f"%{category}%"),
            )
        )
    if skill:
        stmt = stmt.where(Job.skills.any(name=skill))
    if company:
        stmt = stmt.where(Job.company_name.ilike(f"%{company}%"))
    if source:
        stmt = stmt.where(Job.source.has(name=source.lower()))
    if posted_after:
        stmt = stmt.where(Job.posted_at >= posted_after)
    if posted_before:
        stmt = stmt.where(Job.posted_at <= posted_before)
    if salary_min is not None:
        stmt = stmt.where(or_(Job.salary_max >= salary_min, Job.salary_min >= salary_min))
    total_query = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = await session.scalar(total_query) or 0
    jobs = (
        (
            await session.execute(
                stmt.order_by(Job.posted_at.desc().nullslast(), Job.id).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {"total": total, "limit": limit, "offset": offset, "items": [serialize(j) for j in jobs]}


def serialize(j):
    return {
        "id": j.id,
        "source": j.source.name,
        "source_attribution": j.source.attribution,
        "source_job_id": j.source_job_id,
        "company_name": j.company_name,
        "title": j.title,
        "normalized_title": j.normalized_title,
        "description": j.description,
        "description_html": j.description_html,
        "location": j.location,
        "city": j.location_record.city if j.location_record else None,
        "region": j.location_record.region if j.location_record else None,
        "country": j.location_record.country if j.location_record else None,
        "country_code": j.location_record.country_code if j.location_record else None,
        "remote_type": j.remote_type,
        "employment_type": j.employment_type,
        "seniority": j.seniority,
        "department": j.department,
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "salary_period": j.salary_period,
        "posted_at": j.posted_at,
        "updated_at": j.updated_at,
        "apply_url": j.apply_url,
        "source_url": j.source_url,
        "primary_category": j.primary_category,
        "secondary_categories": j.secondary_categories,
        "source_metadata": j.source_metadata,
        "skills": [s.name for s in j.skills],
        "first_seen_at": j.first_seen_at,
        "last_seen_at": j.last_seen_at,
        "closed_at": j.closed_at,
        "status": j.status,
        "content_hash": j.content_hash,
        "raw_data_path": j.raw_data_path,
    }


@router.get("/{job_id}")
async def get_job(job_id: int, session: AsyncSession = Depends(db_session)):
    j = (
        await session.execute(
            select(Job)
            .where(Job.id == job_id)
            .options(
                selectinload(Job.source),
                selectinload(Job.skills),
                selectinload(Job.location_record),
            )
        )
    ).scalar_one_or_none()
    if not j:
        raise HTTPException(404, "Job not found")
    return serialize(j)
