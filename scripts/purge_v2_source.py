"""Delete pilot postings from one source. Defaults to a dry run."""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def purge(source_id: str, execute: bool) -> None:
    url = make_url(settings.database_url).set(database="techjobs_v2").render_as_string(hide_password=False)
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.begin() as conn:
        count = (await conn.execute(text("SELECT count(*) FROM csjobs.postings WHERE source_id=:source_id"), {"source_id": source_id})).scalar_one()
        print(f"source_id={source_id} postings={count} mode={'DELETE' if execute else 'DRY-RUN'}")
        if execute:
            await conn.execute(text("DELETE FROM csjobs.postings WHERE source_id=:source_id"), {"source_id": source_id})
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id", help="Exact csjobs.sources.source_id to purge")
    parser.add_argument("--execute", action="store_true", help="Perform deletion; default is dry-run")
    args = parser.parse_args()
    asyncio.run(purge(args.source_id, args.execute))


if __name__ == "__main__":
    main()
