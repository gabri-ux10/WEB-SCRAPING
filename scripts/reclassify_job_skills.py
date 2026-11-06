"""Recompute specific skills and conservative domain fallbacks for stored jobs."""

from __future__ import annotations

import asyncio
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.classification.skills import (
    DOMAIN_PATTERNS,
    _CONTEXT_SKILL_RULES,
    _compiled_skill_pattern,
    extract_skills,
    infer_contextual_skills,
    infer_domains,
    is_tech_role,
)
from app.database.models import Job, Skill, job_skills
from app.database.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
BATCH_SIZE = 750
EXPORT_FIELDS = (
    "company_name", "posted_at", "job_title", "location", "skills", "url", "is_tech_role"
)


def _posted_stamp(value: str | datetime | None) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _export_key(company: str | None, title: str | None, posted_at: str | datetime | None):
    return ((company or "").strip().casefold(), (title or "").strip().casefold(), _posted_stamp(posted_at))


def classify_job(title: str | None, description: str | None) -> tuple[list[str], list[str]]:
    text = f"{title or ''}\n{description or ''}"
    specific = list(dict.fromkeys(extract_skills(text) + infer_contextual_skills(text)))
    domains = infer_domains(title, description) if not specific else []
    return specific, domains


async def update_database() -> dict[str, int]:
    counts = {"specific": 0, "domain_only": 0, "blank": 0, "processed": 0}
    async with SessionLocal() as session:
        existing_skills = list((await session.scalars(select(Skill))).all())
        skills_by_name = {skill.name: skill for skill in existing_skills}
        all_labels = set(_compiled_skill_pattern()[2])
        all_labels.update(skill for skill, _ in _CONTEXT_SKILL_RULES)
        all_labels.update(f"Domain: {domain}" for domain in DOMAIN_PATTERNS)
        missing_labels = all_labels - skills_by_name.keys()
        if missing_labels:
            session.add_all(Skill(name=name) for name in sorted(missing_labels))
            await session.flush()
            existing_skills = list((await session.scalars(select(Skill))).all())
            skills_by_name = {skill.name: skill for skill in existing_skills}
        last_id = 0
        while True:
            jobs = list((await session.scalars(
                select(Job)
                .where(Job.id > last_id)
                .order_by(Job.id)
                .limit(BATCH_SIZE)
                .options(selectinload(Job.skills))
            )).all())
            if not jobs:
                break
            for job in jobs:
                last_id = job.id
                specific, domains = classify_job(job.title, job.description or job.description_html)
                labels = specific or [f"Domain: {domain}" for domain in domains]
                job.skills = [skills_by_name[label] for label in labels]
                job.is_tech_role = is_tech_role(job.title, labels)
                if specific:
                    counts["specific"] += 1
                elif domains:
                    counts["domain_only"] += 1
                else:
                    counts["blank"] += 1
                counts["processed"] += 1
            await session.commit()
            if counts["processed"] % 3000 < len(jobs):
                print(f"[+] Reclassified {counts['processed']} database jobs...", flush=True)
        print(f"[+] Database pass complete: {counts['processed']} jobs", flush=True)
    return counts


async def export_dataset() -> dict[str, int]:
    json_path = ROOT / "job_postings_full.json"
    csv_path = ROOT / "job_postings_full.csv"
    with json_path.open(encoding="utf-8") as file:
        original_rows = json.load(file)

    async with SessionLocal() as session:
        jobs = list((await session.scalars(
            select(Job).options(selectinload(Job.skills))
        )).all())

    jobs_by_key: dict[tuple, list[Job]] = {}
    for job in jobs:
        jobs_by_key.setdefault(
            _export_key(job.company_name, job.title, job.posted_at), []
        ).append(job)

    counts = {
        "specific": 0, "domain_only": 0, "blank": 0, "exported": 0,
        "tech": 0, "non_tech": 0, "tech_with_skills": 0,
    }
    rows: list[dict] = []
    for original in original_rows:
        row = {field: original.get(field) for field in EXPORT_FIELDS}
        candidates = jobs_by_key.get(
            _export_key(row.get("company_name"), row.get("job_title"), row.get("posted_at")), []
        )
        exact_url_candidates = [
            job for job in candidates if row.get("url") in (job.source_url, job.apply_url)
        ]
        if exact_url_candidates:
            candidates = exact_url_candidates
        names = {skill.name for job in candidates for skill in job.skills}
        # When there is a database match, its skill set is authoritative even
        # when empty; only unmatched export rows retain their prior values.
        if not candidates:
            names = set(original.get("skills") or [])
            if not names:
                _, domains = classify_job(row.get("job_title"), "")
                names = {f"Domain: {domain}" for domain in domains}
        ordered = sorted(names, key=str.casefold)
        specific = [name for name in ordered if not name.startswith("Domain: ")]
        domains = [name for name in ordered if name.startswith("Domain: ")]
        if specific:
            counts["specific"] += 1
            ordered = specific  # A specific match supersedes any stale fallback.
        elif domains:
            counts["domain_only"] += 1
        else:
            counts["blank"] += 1
        row["skills"] = ordered
        if candidates:
            db_flags = {job.is_tech_role for job in candidates}
            row["is_tech_role"] = (
                next(iter(db_flags)) if len(db_flags) == 1
                else is_tech_role(row.get("job_title"), ordered)
            )
        else:
            row["is_tech_role"] = is_tech_role(row.get("job_title"), ordered)
        if row["is_tech_role"]:
            counts["tech"] += 1
            if any(not name.startswith("Domain: ") for name in ordered):
                counts["tech_with_skills"] += 1
        else:
            counts["non_tech"] += 1
        rows.append(row)
        counts["exported"] += 1

    with json_path.open("w", encoding="utf-8", newline="") as file:
        json.dump(rows, file, ensure_ascii=False, indent=2)
        file.write("\n")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            csv_row = row.copy()
            csv_row["skills"] = "; ".join(csv_row["skills"])
            writer.writerow(csv_row)
    print(f"[+] Exported {counts['exported']} records to CSV and JSON", flush=True)
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-only", action="store_true",
        help="Regenerate the consolidated CSV/JSON from already-classified database rows.",
    )
    args = parser.parse_args()
    db_counts = None if args.export_only else await update_database()
    export_counts = await export_dataset()
    async with SessionLocal() as session:
        total_jobs = await session.scalar(select(func.count()).select_from(Job))
        tech_jobs = await session.scalar(
            select(func.count()).select_from(Job).where(Job.is_tech_role.is_(True))
        )
        total_skill_links = await session.scalar(select(func.count()).select_from(job_skills))
    print("\n=== Extraction summary ===")
    print(f"Database records processed: {db_counts['processed'] if db_counts else 'skipped (export-only)'}")
    print(f"Export records: {export_counts['exported']}")
    print(f"Export Tech/Non-Tech: {export_counts['tech']}/{export_counts['non_tech']}")
    print(f"Database Tech/Non-Tech: {tech_jobs}/{total_jobs - tech_jobs}")
    print(f"Database job-skill links: {total_skill_links}")
    populated_tech = export_counts["tech_with_skills"]
    coverage = 100 * populated_tech / export_counts["tech"] if export_counts["tech"] else 0
    print(f"Tech jobs with populated skills: {populated_tech}/{export_counts['tech']} ({coverage:.1f}%)")
    print(f"Export with specific skills: {export_counts['specific']}")
    print(f"Export with domain fallback only: {export_counts['domain_only']}")
    print(f"Export still blank: {export_counts['blank']}")
    if db_counts:
        print(f"Database specific/domain-only/blank: {db_counts['specific']}/{db_counts['domain_only']}/{db_counts['blank']}")


if __name__ == "__main__":
    asyncio.run(main())
