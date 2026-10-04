import hashlib
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    Company,
    DuplicateCandidate,
    Job,
    JobHistory,
    Location,
    Skill,
    Source,
)
from app.deduplication.deduplicator import content_hash, similarity
from app.normalization.locations import normalize_location


async def upsert_job(session, job, company_config, raw_path, duplicate_threshold=1.1):
    source = (
        await session.execute(select(Source).where(Source.name == job.source))
    ).scalar_one_or_none()
    if not source:
        source = Source(
            name=job.source,
            attribution="Credit Jobicy and link to the canonical Jobicy listing."
            if job.source == "jobicy"
            else None,
        )
        session.add(source)
        await session.flush()
    company = (
        await session.execute(
            select(Company).where(
                Company.name == company_config["name"],
                Company.ats == company_config.get("ats"),
                Company.ats_identifier == company_config.get("ats_identifier"),
            )
        )
    ).scalar_one_or_none()
    if not company:
        company = Company(
            name=company_config["name"],
            country=company_config.get("country"),
            region=company_config.get("region"),
            website=company_config.get("website"),
            careers_url=company_config.get("careers_url"),
            ats=company_config.get("ats"),
            ats_identifier=company_config.get("ats_identifier"),
            enabled=company_config.get("enabled", True),
        )
        session.add(company)
        await session.flush()
    if not job.title or not job.company_name or not job.source_job_id:
        return "rejected"
    for candidate_url in (job.apply_url, job.source_url):
        if candidate_url:
            parsed = urlparse(candidate_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return "rejected"
    locdata = normalize_location(job.location, job.country, job.remote_type)
    loc = (
        await session.execute(
            select(Location).where(
                *[getattr(Location, key) == value for key, value in locdata.items()]
            )
        )
    ).scalar_one_or_none()
    if not loc:
        loc = Location(**locdata)
        session.add(loc)
        await session.flush()
    digest = content_hash(job)
    current = datetime.now(UTC)
    existing = (
        await session.execute(
            select(Job)
            .where(Job.source_id == source.id, Job.source_job_id == job.source_job_id)
            .options(selectinload(Job.skills))
        )
    ).scalar_one_or_none()
    if existing:
        if existing.content_hash != digest:
            session.add(
                JobHistory(
                    job_id=existing.id,
                    title=existing.title,
                    description_hash=hashlib.sha256(
                        (existing.description or "").encode()
                    ).hexdigest(),
                    salary_min=existing.salary_min,
                    salary_max=existing.salary_max,
                    salary_currency=existing.salary_currency,
                    location=existing.location,
                    remote_type=existing.remote_type,
                    status=existing.status,
                    content_hash=existing.content_hash,
                    observed_at=current,
                )
            )
            for k, v in job.model_dump(
                exclude={
                    "source",
                    "skills",
                    "city",
                    "region",
                    "country",
                    "country_code",
                    "raw_data_path",
                }
            ).items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            existing.content_hash = digest
            existing.location_id = loc.id
            existing.raw_data_path = raw_path
            outcome = "updated"
        else:
            outcome = "unchanged"
        existing.last_seen_at = current
        existing.missing_runs = 0
        existing.status = "open"
        existing.closed_at = None
        if outcome == "updated":
            skill_records = []
            for skill_name in job.skills:
                skill = (
                    await session.execute(select(Skill).where(Skill.name == skill_name))
                ).scalar_one_or_none()
                if not skill:
                    skill = Skill(name=skill_name)
                    session.add(skill)
                    await session.flush()
                skill_records.append(skill)
            existing.skills = skill_records
    else:
        data = job.model_dump(
            exclude={
                "source",
                "skills",
                "city",
                "region",
                "country",
                "country_code",
                "raw_data_path",
            }
        )
        record = Job(
            **data,
            source_id=source.id,
            company_id=company.id,
            location_id=loc.id,
            content_hash=digest,
            raw_data_path=raw_path,
            first_seen_at=current,
            last_seen_at=current,
            status="open",
            skills=[],
        )
        session.add(record)
        await session.flush()
        outcome = "inserted"
        skill_records = []
        for skill_name in job.skills:
            skill = (
                await session.execute(select(Skill).where(Skill.name == skill_name))
            ).scalar_one_or_none()
            if not skill:
                skill = Skill(name=skill_name)
                session.add(skill)
                await session.flush()
            skill_records.append(skill)
        record.skills = skill_records
        others = (
            (
                await session.execute(
                    select(Job).where(
                        Job.id != record.id,
                        Job.company_name.ilike(job.company_name),
                        Job.status == "open",
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in others:
            score = similarity(job, other)
            if score >= duplicate_threshold:
                a, b = sorted((record.id, other.id))
                session.add(DuplicateCandidate(job_a_id=a, job_b_id=b, score=score))
    return outcome


async def close_missing_jobs(session, company_id, source_id, seen_ids, threshold=2):
    existing = (
        (
            await session.execute(
                select(Job).where(
                    Job.company_id == company_id,
                    Job.source_id == source_id,
                    Job.status == "open",
                )
            )
        )
        .scalars()
        .all()
    )
    closed = 0
    for job in existing:
        if job.source_job_id in seen_ids:
            continue
        job.missing_runs += 1
        if job.missing_runs < threshold:
            continue
        now = datetime.now(UTC)
        session.add(
            JobHistory(
                job_id=job.id,
                title=job.title,
                description_hash=hashlib.sha256((job.description or "").encode()).hexdigest(),
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                location=job.location,
                remote_type=job.remote_type,
                status=job.status,
                content_hash=job.content_hash,
                observed_at=now,
            )
        )
        job.status, job.closed_at = "closed", now
        closed += 1
    return closed
