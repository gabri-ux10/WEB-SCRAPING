import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.main import app
from app.api.routes.jobs import db_session
from app.database.models import Base
from app.persistence.jobs import upsert_job
from app.schemas.job import NormalizedJob


@pytest.mark.asyncio
async def test_jobs_api_filters_and_returns_attribution():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    job = NormalizedJob(
        source="jobicy",
        source_job_id="123",
        company_name="Example",
        title="Remote Software Engineer",
        description="Python APIs",
        location="Remote - Kenya",
        remote_type="remote",
        primary_category="Software Engineering",
        skills=["Python"],
        source_url="https://jobicy.com/jobs/123",
        apply_url="https://jobicy.com/jobs/123",
    )
    async with sessions() as session:
        await upsert_job(
            session,
            job,
            {"name": "Example", "ats": "jobicy", "ats_identifier": "jobicy"},
            "snapshot.json",
        )
        await session.commit()

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[db_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/jobs", params={"country": "KE", "region": "africa", "skill": "Python"}
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["total"] == 1
            assert payload["items"][0]["source_url"] == "https://jobicy.com/jobs/123"
            assert payload["items"][0]["source_attribution"]
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
