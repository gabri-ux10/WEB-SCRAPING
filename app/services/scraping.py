import json
import logging
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from sqlalchemy import select

from app.classification.classifier import enrich_classification
from app.collectors.aggregators import AdzunaCollector, JoobleCollector, USAJobsCollector
from app.collectors.ashby import AshbyCollector
from app.collectors.greenhouse import GreenhouseCollector
from app.collectors.jobicy import JobicyCollector
from app.collectors.lever import LeverCollector
from app.config import ROOT
from app.config import settings as app_settings
from app.database.models import Company, Job, ScrapeError, ScrapeRun, Source
from app.database.session import SessionLocal
from app.normalization.normalize import enrich
from app.persistence.jobs import close_missing_jobs, upsert_job

log = logging.getLogger(__name__)
COLLECTORS = {
    "greenhouse": GreenhouseCollector,
    "lever": LeverCollector,
    "ashby": AshbyCollector,
    "adzuna": AdzunaCollector,
    "usajobs": USAJobsCollector,
    "jooble": JoobleCollector,
    "jobicy": JobicyCollector,
}


def read_yaml(path, default):
    p = ROOT / path
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else default


def save_raw(source, key, payload):
    day = datetime.now(UTC).date().isoformat()
    directory = ROOT / "data" / "raw" / day / source
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", key).strip("_")[:90] or "response"
    path = directory / f"{slug}_{uuid.uuid4().hex[:8]}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return str(path.relative_to(ROOT))


async def scrape(
    source_filter=None,
    country=None,
    region=None,
    company_name=None,
    dry_run=False,
    max_pages=None,
    max_jobs=None,
):
    registry = read_yaml(Path("config/companies.yml"), [])
    settings = read_yaml(Path("config/sources.yml"), {"sources": {}})
    terms = read_yaml(Path("config/search_terms.yml"), {"technology_search_terms": {}}).get(
        "technology_search_terms", {}
    )
    regions = read_yaml(Path("config/regions.yml"), {"regions": {}}).get("regions", {})
    selected_countries = (
        [country.upper()]
        if country
        else (regions.get(region.lower(), {}).get("countries", []) if region else [])
    )
    companies = [c for c in registry if c.get("enabled")]
    if company_name:
        companies = [c for c in companies if c.get("name", "").lower() == company_name.lower()]
    if country:
        companies = [c for c in companies if c.get("country") == country.upper()]
    if region:
        rc = regions.get(region.lower(), {}).get("countries", [])
        companies = [
            c
            for c in companies
            if c.get("country") in rc or (c.get("region", "").lower() == region.lower())
        ]
    summary = {
        "run_id": str(uuid.uuid4()),
        "found": 0,
        "inserted": 0,
        "updated": 0,
        "closed": 0,
        "rejected": 0,
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
    }
    run_started = time.monotonic()
    source_last_request = {}
    async with SessionLocal() as session:
        for name, cls in COLLECTORS.items():
            source_cfg = settings.get("sources", {}).get(name, {})
            if source_filter and name != source_filter:
                continue
            if not source_cfg.get("enabled", False):
                continue
            if name == "adzuna" and not (
                app_settings.adzuna_app_id and app_settings.adzuna_app_key
            ):
                log.info("source=%s disabled: credentials not configured", name)
                continue
            if name == "usajobs" and not (
                app_settings.usajobs_api_key and app_settings.usajobs_email
            ):
                log.info("source=%s disabled: credentials not configured", name)
                continue
            if name == "jooble" and not (
                app_settings.jooble_api_key
                or any(
                    os.getenv(market.get("key_env", "JOOBLE_API_KEY"))
                    for market in source_cfg.get("markets", [])
                )
            ):
                log.info("source=%s disabled: credentials not configured", name)
                continue
            targets = [c for c in companies if c.get("ats") == name]
            if name in {"adzuna", "usajobs", "jooble", "jobicy"} and not targets:
                targets = [
                    {
                        "name": name.title(),
                        "country": None,
                        "region": "global",
                        "ats": name,
                        "ats_identifier": name,
                        "enabled": True,
                    }
                ]
            if not targets and name in {"greenhouse", "lever", "ashby"}:
                continue
            for config in targets:
                summary["attempted"] += 1
                collector = cls()
                collector._last_request = source_last_request.get(name, 0.0)
                collector.request_interval = 1 / max(
                    0.1, float(source_cfg.get("rate_limit_per_second", 2))
                )
                try:
                    cfg = {
                        **source_cfg,
                        "max_pages": max_pages or source_cfg.get("max_pages", 2),
                        "max_jobs": max_jobs or source_cfg.get("max_jobs", 100),
                        "keywords": [v for vals in terms.values() for v in vals]
                        if name in {"adzuna", "usajobs", "jooble"}
                        else source_cfg.get("keywords", []),
                    }
                    if name == "adzuna" and selected_countries:
                        cfg["countries"] = [code.lower() for code in selected_countries]
                    elif name == "adzuna" and not cfg.get("countries"):
                        cfg["countries"] = (
                            [config["country"].lower()] if config.get("country") else []
                        )
                    if name == "jooble" and selected_countries:
                        locations = source_cfg.get("country_locations", {})
                        cfg["countries"] = [
                            locations[code] for code in selected_countries if code in locations
                        ]
                        if cfg.get("markets"):
                            cfg["markets"] = [
                                market
                                for market in cfg["markets"]
                                if market.get("country_code") in selected_countries
                            ]
                    elif name == "jooble" and not cfg.get("countries"):
                        cfg["countries"] = [config["country"] or "Kenya"]
                    raw_jobs = await collector.fetch({**config, **cfg})
                    raw_path = save_raw(name, config["name"], raw_jobs)
                    for idx, payload in enumerate(collector.raw_responses):
                        save_raw(name, f"{config['name']}_request_{idx + 1}", payload)
                    summary["succeeded"] += 1
                    summary["found"] += len(raw_jobs)
                    log.info(
                        "source=%s company=%s jobs_found=%d", name, config["name"], len(raw_jobs)
                    )
                    if dry_run:
                        continue
                    seen_ids = set()
                    record_errors = 0
                    company_rejections = 0
                    for raw in raw_jobs[: max_jobs or cfg["max_jobs"]]:
                        try:
                            job = enrich(collector.normalize(raw, config))
                            enrich_classification(job)
                            job.raw_data_path = raw_path
                            if not job.source_job_id or not job.title or not job.company_name:
                                summary["rejected"] += 1
                                company_rejections += 1
                                continue
                            seen_ids.add(job.source_job_id)
                            async with session.begin_nested():
                                outcome = await upsert_job(
                                    session,
                                    job,
                                    config,
                                    raw_path,
                                    float(
                                        settings.get("scraping", {}).get(
                                            "duplicate_threshold", 0.92
                                        )
                                    ),
                                )
                            if outcome in {"inserted", "updated"}:
                                summary[outcome] += 1
                            elif outcome == "rejected":
                                summary["rejected"] += 1
                                company_rejections += 1
                        except Exception as exc:
                            record_errors += 1
                            summary["errors"].append(f"{name}/{config['name']}: record: {exc}")
                            log.exception("job normalization/persistence failed")
                    if record_errors:
                        summary["failed"] += 1
                        summary["succeeded"] -= 1
                        summary["errors"].append(
                            f"{name}/{config['name']}: {record_errors} record(s) failed"
                        )
                    elif not company_rejections and source_cfg.get(
                        "close_missing", name in {"greenhouse", "lever", "ashby"}
                    ):
                        company = (
                            await session.execute(
                                select(Company).where(
                                    Company.name == config["name"],
                                    Company.ats == config.get("ats"),
                                    Company.ats_identifier == config.get("ats_identifier"),
                                )
                            )
                        ).scalar_one_or_none()
                        source = (
                            await session.execute(select(Source).where(Source.name == name))
                        ).scalar_one_or_none()
                        if company and source:
                            threshold = int(
                                settings.get("scraping", {}).get("missing_runs_before_closing", 2)
                            )
                            summary["closed"] += await close_missing_jobs(
                                session, company.id, source.id, seen_ids, threshold
                            )
                    await session.commit()
                except Exception as exc:
                    for idx, payload in enumerate(collector.raw_responses):
                        save_raw(name, f"{config['name']}_request_{idx + 1}", payload)
                    await session.rollback()
                    summary["failed"] += 1
                    summary["errors"].append(f"{name}/{config['name']}: {exc}")
                    session.add(
                        ScrapeError(
                            run_id=summary["run_id"],
                            source=name,
                            company=config["name"],
                            message=str(exc),
                        )
                    )
                    await session.commit()
                    log.warning("source=%s company=%s error=%s", name, config["name"], exc)
                finally:
                    source_last_request[name] = collector._last_request
                    await collector.close()
        if not dry_run:
            # Close only after repeated full-source missing observations; failures and empty unconfigured feeds never close jobs.
            pass
        elapsed = time.monotonic() - run_started
        session.add(
            ScrapeRun(
                run_id=summary["run_id"],
                source=source_filter,
                connector=source_filter,
                started_at=datetime.fromtimestamp(time.time() - elapsed, UTC),
                finished_at=datetime.now(UTC),
                companies_attempted=summary["attempted"],
                companies_succeeded=summary["succeeded"],
                companies_failed=summary["failed"],
                jobs_found=summary["found"],
                jobs_inserted=summary["inserted"],
                jobs_updated=summary["updated"],
                jobs_closed=summary["closed"],
                duration=elapsed,
                status="partial" if summary["failed"] else "success",
                error_summary="\n".join(summary["errors"]) or None,
            )
        )
        await session.commit()
    return summary


async def export_jobs(fmt="csv", output=None):
    import csv

    from sqlalchemy.orm import selectinload

    async with SessionLocal() as session:
        jobs = (
            (
                await session.execute(
                    select(Job).options(
                        selectinload(Job.source),
                        selectinload(Job.skills),
                        selectinload(Job.location_record),
                    )
                )
            )
            .scalars()
            .all()
        )
        records = []
        for j in jobs:
            row = {
                k: getattr(j, k)
                for k in (
                    "id",
                    "source_job_id",
                    "company_name",
                    "title",
                    "normalized_title",
                    "description",
                    "location",
                    "remote_type",
                    "employment_type",
                    "salary_min",
                    "salary_max",
                    "salary_currency",
                    "salary_period",
                    "posted_at",
                    "apply_url",
                    "source_url",
                    "primary_category",
                    "secondary_categories",
                    "source_metadata",
                    "status",
                    "content_hash",
                )
            }
            row["source"] = j.source.name
            row["source_attribution"] = j.source.attribution
            row["skills"] = [s.name for s in j.skills]
            row["country_code"] = j.location_record.country_code if j.location_record else None
            records.append(
                {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}
            )
    out = Path(output) if output else ROOT / "data" / "exports" / f"jobs.{fmt}"
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "jsonl":
        out.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
        )
    elif fmt == "csv":
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=list(records[0])
                if records
                else ["id", "source", "company_name", "title"],
            )
            writer.writeheader()
            writer.writerows(records)
    else:
        raise ValueError("format must be csv, json, or jsonl")
    return str(out)
