from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Company
from app.database.session import SessionLocal

router = APIRouter(prefix="/companies", tags=["companies"])


async def db_session():
    async with SessionLocal() as session:
        yield session


@router.get("")
async def companies(session: AsyncSession = Depends(db_session)):
    rows = (await session.execute(select(Company).order_by(Company.name))).scalars().all()
    return [
        {
            k: getattr(c, k)
            for k in (
                "id",
                "name",
                "country",
                "region",
                "website",
                "careers_url",
                "ats",
                "ats_identifier",
                "enabled",
            )
        }
        for c in rows
    ]


@router.get("/{company_id}")
async def company(company_id: int, session: AsyncSession = Depends(db_session)):
    c = (
        await session.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Company not found")
    return {
        k: getattr(c, k)
        for k in (
            "id",
            "name",
            "country",
            "region",
            "website",
            "careers_url",
            "ats",
            "ats_identifier",
            "enabled",
        )
    }
