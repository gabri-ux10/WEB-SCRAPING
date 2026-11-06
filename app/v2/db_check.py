"""Read-only counts for the v2 PostgreSQL schema; never prints connection details."""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.v2.envfile import load_selected_env

TABLES = {
    "categories": "categories",
    "sub-domains": "sub_domains",
    "skills": "skills",
    "sources": "sources",
    "evidence rows": "source_evidence",
    "company leads": "companies",
    "ATS board leads": "ats_boards",
    "postings": "postings",
    "raw payloads": "raw_payloads",
}


async def main() -> None:
    root = Path(__file__).resolve().parents[2]
    configured = load_selected_env(root / ".env", {"DATABASE_URL"}).get("DATABASE_URL")
    if not configured or "<" in configured or ">" in configured:
        print("DATABASE_URL_MISSING_OR_PLACEHOLDER; restore it in the existing .env before checking PostgreSQL.")
        raise SystemExit(2)
    url = make_url(configured).set(database="techjobs_v2")
    engine = create_async_engine(url, pool_pre_ping=True, connect_args={"timeout": 10})
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            for label, table in TABLES.items():
                count = (await connection.execute(text(f'SELECT count(*) FROM csjobs."{table}"'))).scalar_one()
                print(f"{label}: {count}")
    except Exception as exc:
        chain = []
        current = exc
        while current is not None and current not in chain:
            chain.append(current)
            current = getattr(current, "__cause__", None) or getattr(current, "__context__", None) or getattr(current, "orig", None)
        names = {type(item).__name__ for item in chain}
        if "InvalidPasswordError" in names or "InvalidAuthorizationSpecificationError" in names:
            reason = "AUTHENTICATION_FAILED"
        elif "InvalidCatalogNameError" in names:
            reason = "DATABASE_NOT_FOUND"
        elif "UndefinedTableError" in names or "UndefinedSchemaError" in names:
            reason = "SCHEMA_MISSING_OR_MIGRATIONS_PENDING"
        elif "gaierror" in names:
            reason = "DNS_RESOLUTION_FAILED"
        elif "ConnectionRefusedError" in names:
            reason = "TCP_CONNECTION_REFUSED_SERVICE_MAY_BE_STOPPED"
        elif "TimeoutError" in names:
            reason = "CONNECTION_TIMEOUT"
        else:
            reason = "CONNECTION_OR_SCHEMA_ERROR"
        print(f"DATABASE_CHECK_FAILED:{reason}; connection details were not printed.")
        raise SystemExit(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
