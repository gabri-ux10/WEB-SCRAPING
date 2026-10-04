from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Job, Source
from app.database.session import SessionLocal

router = APIRouter(tags=["sources"])


async def db_session():
    async with SessionLocal() as session:
        yield session


@router.get("/sources")
async def sources(session: AsyncSession = Depends(db_session)):
    rows = (await session.execute(select(Source))).scalars().all()
    return [{"id": s.id, "name": s.name, "attribution": s.attribution} for s in rows]


@router.get("/stats")
async def stats(session: AsyncSession = Depends(db_session)):
    total = await session.scalar(select(func.count()).select_from(Job))
    opened = await session.scalar(select(func.count()).select_from(Job).where(Job.status == "open"))
    return {"jobs_total": total or 0, "jobs_open": opened or 0}
