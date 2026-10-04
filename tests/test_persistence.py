import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.models import Base
from app.persistence.jobs import close_missing_jobs, upsert_job
from app.schemas.job import NormalizedJob


@pytest.mark.asyncio
async def test_idempotent_insert_and_change_history():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    cfg = {
        "name": "Acme",
        "ats": "greenhouse",
        "ats_identifier": "acme",
        "country": "KE",
        "enabled": True,
    }
    job = NormalizedJob(
        source="greenhouse",
        source_job_id="one",
        company_name="Acme",
        title="Backend Engineer",
        description="Python",
        location="Nairobi, Kenya",
        skills=["Python"],
    )
    async with sessions() as s:
        assert await upsert_job(s, job, cfg, "raw.json") == "inserted"
        await s.commit()
    async with sessions() as s:
        assert await upsert_job(s, job, cfg, "raw.json") == "unchanged"
        await s.commit()
        changed = job.model_copy(update={"description": "Go", "skills": ["Go"]})
        assert await upsert_job(s, changed, cfg, "raw2.json") == "updated"
        await s.commit()
    from sqlalchemy import func, select

    from app.database.models import Company, Job, JobHistory, Source

    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(Job)) == 1
        assert await s.scalar(select(func.count()).select_from(JobHistory)) == 1
        company = await s.scalar(select(Company))
        source = await s.scalar(select(Source))
        assert await close_missing_jobs(s, company.id, source.id, set(), threshold=1) == 1
        await s.commit()
        job_row = await s.scalar(select(Job))
        assert job_row.status == "closed" and job_row.closed_at is not None
        assert await s.scalar(select(func.count()).select_from(JobHistory)) == 2
    await engine.dispose()
