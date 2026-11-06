"""Read legacy URLs/companies as leads; write only board and company metadata to v2."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url

from app.config import settings
from app.v2.database import ATSBoard, Company, Source
from app.v2.normalization import normalize_company_name

ATS_HOSTS = {
    "greenhouse": {"boards.greenhouse.io", "job-boards.greenhouse.io", "boards-api.greenhouse.io"},
    "lever": {"jobs.lever.co", "jobs.eu.lever.co"},
    "ashby": {"jobs.ashbyhq.com"},
}
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,127}$")


def extract_board(source_name: str, url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    ats = next((name for name, hosts in ATS_HOSTS.items() if host in hosts), None)
    if not ats or (source_name.lower() != ats and not source_name.lower().startswith("export")):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    identifier = parts[0]
    if identifier in {"v0", "v1", "api"} and len(parts) > 1:
        identifier = parts[1]
    if not SLUG.fullmatch(identifier) or identifier.lower() in {"jobs", "postings", "boards"}:
        return None
    return identifier


async def main() -> None:
    target_url = make_url(settings.database_url).set(database="techjobs_v2").render_as_string(hide_password=False)
    legacy_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    v2_engine = create_async_engine(target_url, pool_pre_ping=True)
    Session = async_sessionmaker(v2_engine, expire_on_commit=False)
    rows = []
    async with legacy_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT s.name AS source_name,j.company_name,j.source_url,j.apply_url
            FROM jobs j JOIN sources s ON s.id=j.source_id
            ORDER BY j.id
        """))
        rows = [dict(row._mapping) for row in result]
    companies: dict[str, str] = {}
    boards: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        display = (row["company_name"] or "").strip()
        key = normalize_company_name(display)
        if key:
            companies.setdefault(key, display)
        for url in (row["source_url"], row["apply_url"]):
            board = extract_board(row["source_name"] or "", url)
            if board:
                host = (urlparse(url).hostname or "").lower()
                ats = "lever" if host in ATS_HOSTS["lever"] else "ashby" if host in ATS_HOSTS["ashby"] else "greenhouse"
                boards.setdefault((ats, board), set()).add(key)

    async with Session() as session, session.begin():
        company_rows = {}
        for key, display in companies.items():
            company = (await session.execute(select(Company).where(Company.normalized_key == key))).scalar_one_or_none()
            if company is None:
                company = Company(display_name=display, normalized_key=key)
                session.add(company)
                await session.flush()
            company_rows[key] = company
        for (ats, identifier), company_keys in boards.items():
            source_id = ats
            source = await session.get(Source, source_id)
            if source is None:
                continue
            for key in company_keys:
                existing = (await session.execute(select(ATSBoard).where(
                    ATSBoard.source_id == source_id, ATSBoard.identifier == identifier,
                ))).scalar_one_or_none()
                if existing is None:
                    session.add(ATSBoard(
                        source_id=source_id, identifier=identifier,
                        company_id=company_rows.get(key).id if key in company_rows else None,
                        discovered_from="legacy job/apply URL", verified_name_match=None,
                        last_status="legacy_lead_unverified",
                    ))
    await legacy_engine.dispose()
    await v2_engine.dispose()
    print(f"Loaded {len(companies)} normalized company leads and {len(boards)} distinct unverified ATS board identifiers into v2; no postings were copied.")


if __name__ == "__main__":
    asyncio.run(main())
