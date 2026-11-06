"""Create and seed the isolated UTF8 v2 database; never connects to legacy tables for writes."""

from __future__ import annotations

import asyncio
import csv
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.v2.database import (
    ATSBoard, Category, ClassificationFallback, Company, Posting, PostingSkill,
    RawPayload, ScrapeRun, Skill, Source, SourceEvidence, SubDomain,
    TranslationCache, V2Base,
)
from app.v2.taxonomy import REFERENCE_DIR

DATABASE_NAME = "techjobs_v2"


async def ensure_database(target_url: str) -> None:
    target = make_url(target_url)
    admin = make_url(settings.database_url).set(database="postgres")
    conn = await asyncpg.connect(
        host=admin.host,
        port=admin.port or 5432,
        user=admin.username,
        password=admin.password,
        database=admin.database,
    )
    try:
        encoding = await conn.fetchval("SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname=$1", target.database)
        if encoding:
            if encoding.upper() != "UTF8":
                raise RuntimeError(f"Target {DATABASE_NAME} exists with non-UTF8 encoding")
            return
        await conn.execute(f'CREATE DATABASE "{DATABASE_NAME}" WITH ENCODING \'UTF8\' TEMPLATE template0')
    finally:
        await conn.close()


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


async def seed(target_url: str) -> None:
    engine = create_async_engine(target_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        encoding = (await conn.exec_driver_sql("SHOW server_encoding")).scalar_one()
        if encoding.upper() != "UTF8":
            raise RuntimeError("v2 database must use UTF8 encoding")
        await conn.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS csjobs")
        await conn.run_sync(V2Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    taxonomy = json.loads((REFERENCE_DIR / "cs_job_taxonomy_v2.json").read_text(encoding="utf-8"))
    source_rows = read_rows(REFERENCE_DIR / "scrape_sources_v2.csv")
    evidence_rows = read_rows(REFERENCE_DIR / "source_terms_decisions_v2.csv")
    evidence_by_source = {row["source_id"]: row for row in evidence_rows}
    vocabulary = read_rows(REFERENCE_DIR / "skills_vocabulary_v2.csv")
    async with session_factory() as session, session.begin():
        for category in taxonomy["categories"]:
            await session.merge(Category(id=category["id"], name=category["name"], tier=category["tier"]))
            for subdomain in category["subdomains"]:
                await session.merge(SubDomain(
                    id=subdomain["id"], category_id=category["id"], name=subdomain["name"],
                    roadmap=subdomain.get("roadmap"), roadmap_node_count=subdomain.get("roadmap_node_count", 0),
                    tier=subdomain.get("tier", category["tier"]), source=subdomain.get("source", "roadmap.sh"),
                    normalized_roles=subdomain.get("normalized_roles", []),
                    title_aliases=subdomain.get("title_aliases", []),
                    title_aliases_i18n=subdomain.get("title_aliases_i18n", {}),
                ))
        for fallback_id, fallback in taxonomy["fallback_categories"].items():
            await session.merge(ClassificationFallback(
                id=fallback_id, name=fallback["name"], sub_domain=fallback["sub_domain"], use_when=fallback["use_when"]
            ))
        for row in vocabulary:
            await session.merge(Skill(
                slug=row["slug"], label=row.get("label", ""), n_roadmaps=int(row.get("n_roadmaps") or 0),
                roadmaps=[x for x in (row.get("roadmaps") or "").split(";") if x],
                subdomain_ids=[x for x in (row.get("subdomain_ids") or "").split(";") if x],
                n_subdomains=int(row.get("n_subdomains") or 0),
            ))
        for row in source_rows:
            terms = evidence_by_source.get(row["source_id"], {})
            # The dated verification/terms ledger is authoritative for eligibility.
            current_status = terms.get("verification_status", "NOT_REVIEWED")
            terms_decision = terms.get("terms_decision", "not_reviewed")
            await session.merge(Source(
                id=row["source_id"], name=row["source"], source_type=row["type"],
                regions=[x.strip() for x in row["regions"].split(";") if x.strip()],
                access=row["access"], auth=row["auth"], verification_status=current_status,
                evidence=terms.get("evidence_url") or row["evidence"], limits_and_terms=row["limits_and_terms"],
                enable_from_stage=row["enable_from_stage"], priority=int(row["priority"]) if row["priority"].isdigit() else None,
                terms_decision=terms_decision, enabled=False,
            ))
            if terms:
                existing_evidence = (await session.execute(select(SourceEvidence).where(
                    SourceEvidence.source_id == row["source_id"],
                    SourceEvidence.evidence_url == terms["evidence_url"],
                ))).scalar_one_or_none()
                if existing_evidence is None:
                    session.add(SourceEvidence(
                        source_id=row["source_id"], evidence_url=terms["evidence_url"],
                        checked_on=datetime.fromisoformat(terms["checked_on"]).replace(tzinfo=UTC),
                        decision=terms["terms_decision"], notes=terms["notes"],
                    ))
                else:
                    existing_evidence.checked_on = datetime.fromisoformat(terms["checked_on"]).replace(tzinfo=UTC)
                    existing_evidence.decision = terms["terms_decision"]
                    existing_evidence.notes = terms["notes"]
    await engine.dispose()


async def main() -> None:
    target_url = os.getenv("DATABASE_URL_V2")
    if not target_url:
        target_url = make_url(settings.database_url).set(database=DATABASE_NAME).render_as_string(hide_password=False)
    await ensure_database(target_url)
    await seed(target_url)
    print("Created/seeded isolated techjobs_v2 database with v2 reference rows; no postings were inserted.")


if __name__ == "__main__":
    asyncio.run(main())
