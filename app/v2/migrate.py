"""Apply the bounded v2 schema updates to the isolated techjobs_v2 database."""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.v2.database import V2Base


async def main() -> None:
    target = make_url(settings.database_url).set(database="techjobs_v2")
    engine = create_async_engine(target, pool_pre_ping=True, connect_args={"timeout": 10})
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE SCHEMA IF NOT EXISTS csjobs"))
            await connection.run_sync(V2Base.metadata.create_all)
            await connection.execute(text("ALTER TABLE csjobs.postings ALTER COLUMN clean_title_en DROP NOT NULL"))
        print("V2 schema migration applied to techjobs_v2.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
