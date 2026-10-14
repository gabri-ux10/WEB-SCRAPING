#!/usr/bin/env python3
"""
mass_scrape.py — High-throughput concurrent tech-job scraper.

Fires all configured sources + expanded company boards in parallel via asyncio,
persists into PostgreSQL (dedup by source+source_job_id unique constraint),
falls back to JSONL when the database is unavailable, and prints real-time
progress to the terminal.

Usage:
    python mass_scrape.py                     # scrape enabled sources to exhaustion
    python mass_scrape.py --workers 10        # limit to 10 concurrent HTTP requests
    python mass_scrape.py --jsonl-only        # skip PostgreSQL, write JSONL only
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import UTC, datetime, date
from pathlib import Path

import httpx

# ── Ensure project root is on sys.path so `app.*` imports resolve ──
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.classification.classifier import enrich_classification
from app.collectors.aggregators import AdzunaCollector, JoobleCollector, USAJobsCollector
from app.collectors.arbeitnow import ArbeitnowCollector
from app.collectors.ashby import AshbyCollector
from app.collectors.greenhouse import GreenhouseCollector
from app.collectors.jobicy import JobicyCollector
from app.collectors.himalayas import HimalayasCollector
from app.collectors.lever import LeverCollector
from app.collectors.remotive import RemotiveCollector
from app.collectors.remoteok import RemoteOKCollector
from app.config import settings as app_settings
from app.normalization.normalize import enrich
from app.schemas.job import NormalizedJob

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mass_scrape")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _make_collector(collector_cls):
    """Build a collector with a hard 10-second timeout for every HTTP request."""
    collector = collector_cls()
    collector.client.timeout = httpx.Timeout(10.0)
    return collector


# =====================================================================
# Expanded company list — Greenhouse, Lever, Ashby boards
# =====================================================================

EXTRA_GREENHOUSE = [
    "airbnb", "airtable", "amplitude", "asana", "aurora", "benchling",
    "bolt", "braze", "calm", "canva", "chainalysis", "chime",
    "circle", "confluent", "coreweave", "cruise", "deel",
    "doordash", "duolingo", "faire", "fivetran", "flexport",
    "gusto", "hashicorp", "hinge", "hubspot", "improbable",
    "intercom", "justworks", "klarna", "lattice",
    "lyft", "marqeta", "medium", "miro",
    "nerdwallet", "newrelic", "niantic", "noom",
    "nuro", "okta", "onemedical", "opendoor", "opsramp",
    "outreach", "pagerduty", "palantir", "plaid", "podium",
    "relativity", "retool", "robinhood", "samsara",
    "scalevector", "scribd", "seatgeek", "segment",
    "sendgrid", "shopify", "silverfort", "snapchat",
    "snyk", "sofi", "squarespace", "sweetgreen",
    "taskrabbit", "thetradedesk", "thumbtack", "tinder",
    "toast", "toptal", "truebill", "turbotax",
    "udemy", "unity", "upstart", "vanta",
    "waymo", "webflow", "wish", "wiz",
    "zapier", "zendesk", "zoominfo", "zynga",
    "anduril", "anthropic", "applied-intuition", "astranis",
    "aurora-solar", "benchling", "brinqa", "cerebras",
    "checkout", "chronosphere", "contentful", "cribl",
    "crossbeam", "datto", "deepmind", "dnb", "dolby",
    "etsy", "figma", "formlabs", "glossier", "grammarly",
    "immuta", "lacework", "materialize", "nextdoor",
    "okcupid", "onestream", "optiver", "orca-security",
    "ownbackup", "pax8", "personio", "pipedrive",
    "procore", "productboard", "rapid7", "recurly",
    "redpanda-data", "remote", "reportlinker",
    "rippling", "riskified", "salesloft",
    "sambanova", "sentry", "sisense",
    "smartbear", "smartsheet", "snorkel",
    "snowflake", "splunk", "strava",
    "strongdm", "superhuman", "tanium",
    "tessian", "toasttab", "uipath",
    "verkada", "wealthsimple", "whatnot",
    "workrise", "yotpo", "zscaler",
]

EXTRA_LEVER = [
    "netflix", "coinbase", "nextroll", "lucidmotors",
    "masterclass", "nianticlabs", "relativityspace",
    "rivian", "peloton", "getaround", "foursquare",
    "thumbtack", "grammarly", "lever",
    "handshake", "justworks", "komodohealth",
    "mux", "netlify", "opendoor",
    "postman", "productboard", "quizlet",
    "ro", "samsara", "talkdesk",
    "twitch", "underdog", "attentive",
    "benchling", "carta", "convoy",
    "discord", "dutchie", "everlaw",
    "forethought", "ironclad", "lacework",
    "loom", "mparticle", "navan",
    "notarize", "olo", "packetfabric",
    "personalcapital", "qualtrics", "redfin",
    "scale", "snorkelai", "strike",
    "trueaccord", "applovin", "clearcover",
]

EXTRA_ASHBY = [
    "anthropic", "anyscale", "baseten",
    "causal", "cohere", "coreweave",
    "dbt-labs", "glean", "helion",
    "jasper-ai", "lambda", "mux",
    "perplexity-ai", "planetary",
    "runway", "scaleai", "sourcegraph",
    "stability-ai", "standard-ai", "together-ai",
    "weights-biases", "neon", "fireworks-ai",
    "mistral", "brev-dev",
    "clerk", "defer", "depot",
    "fly", "inngest", "livekit",
    "materialize", "oso", "planetscale",
    "prefect", "prisma", "railway",
    "render", "retool", "sanity",
    "sequin", "stainlessapi", "turso",
    "upstash", "zephyr-ai",
]

# Deduplicate identifiers that are already in config/companies.yml
_EXISTING_GH = {
    "figma", "stripe", "databricks", "cloudflare", "coinbase",
    "discord", "reddit", "gitlab", "elastic", "mongodb",
    "twilio", "cockroachlabs", "grafanalabs", "brex", "gusto",
    "instacart", "deliveroo",
}
_EXISTING_LEVER = {"spotify", "palantir"}
_EXISTING_ASHBY = {
    "linear", "openai", "ramp", "notion", "vercel",
    "supabase", "resend", "replit", "posthog", "modal", "pinecone",
}


# =====================================================================
# Progress tracker (thread/coroutine-safe via asyncio)
# =====================================================================

class Progress:
    def __init__(self):
        self.total_fetched = 0
        self.unique_stored = 0
        self.duplicates = 0
        self.errors = 0
        self.sources_done = 0
        self.sources_total = 0
        self.source_states: dict[str, str] = {}
        self.retry_queue: list[dict] = []
        self._lock = asyncio.Lock()
        self._start = time.monotonic()

    async def add(self, *, fetched: int = 0, stored: int = 0, dupes: int = 0, errs: int = 0):
        async with self._lock:
            self.total_fetched += fetched
            self.unique_stored += stored
            self.duplicates += dupes
            self.errors += errs

    async def source_done(self):
        async with self._lock:
            self.sources_done += 1

    async def source_state(self, name: str, state: str, retries: list[dict] | None = None):
        async with self._lock:
            self.source_states[name] = state
            if retries:
                self.retry_queue.extend(retries)

    def line(self) -> str:
        elapsed = time.monotonic() - self._start
        rate = self.unique_stored / elapsed if elapsed > 0 else 0
        return (
            f"[+] Stored {self.unique_stored:,} unique  |  "
            f"fetched {self.total_fetched:,}  |  dupes {self.duplicates:,}  |  "
            f"errs {self.errors:,}  |  sources {self.sources_done}/{self.sources_total}  |  "
            f"{rate:.0f} jobs/s  |  {elapsed:.0f}s"
        )


# =====================================================================
# Database helpers
# =====================================================================

_db_available: bool | None = None
_jsonl_path: Path | None = None
EXPORT_FIELDS = ["company_name", "posted_at", "job_title", "location", "skills", "url"]
_export_rows: dict[tuple[str, str, str], dict] = {}
_seen_composite_keys: set[tuple[str, str, str]] = set()


def _composite_key(job: NormalizedJob) -> tuple[str, str, str]:
    posted_at = job.posted_at.isoformat() if hasattr(job.posted_at, "isoformat") else str(job.posted_at or "")
    return ((job.company_name or "").strip().casefold(), (job.title or "").strip().casefold(), posted_at.strip())


def _capture_export_rows(jobs: list[NormalizedJob]) -> None:
    """Keep one normalized row per requested company/title/date key."""
    for job in jobs:
        url = job.source_url or job.apply_url or ""
        identity = _composite_key(job)
        posted_at = job.posted_at
        _export_rows.setdefault(
            identity,
            {
                "company_name": job.company_name or "Unknown",
                "posted_at": posted_at.isoformat() if hasattr(posted_at, "isoformat") else (str(posted_at) if posted_at else ""),
                "job_title": job.title or "",
                "location": job.location or "",
                "skills": list(job.skills or []),
                "url": url,
            },
        )


def _write_exports() -> tuple[Path, Path, int]:
    """Write the consolidated run dataset to JSON and CSV using the same field set."""
    records = list(_export_rows.values())
    json_path = PROJECT_ROOT / "job_postings_full.json"
    csv_path = PROJECT_ROOT / "job_postings_full.csv"
    json_tmp = json_path.with_suffix(".json.tmp")
    csv_tmp = csv_path.with_suffix(".csv.tmp")

    with json_tmp.open("w", encoding="utf-8") as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    with csv_tmp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in records:
            writer.writerow({**row, "skills": "; ".join(row["skills"])})

    json_tmp.replace(json_path)
    csv_tmp.replace(csv_path)
    log.info("Exported %s unique postings to %s and %s", len(records), csv_path.name, json_path.name)
    return csv_path, json_path, len(records)


def _load_existing_export() -> int:
    """Resume a partial run by loading its previously exported unique records."""
    path = PROJECT_ROOT / "job_postings_full.json"
    if not path.exists():
        return 0
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not resume existing export {path.name}") from exc
    for row in rows:
        if not isinstance(row, dict):
            continue
        identity = (
            str(row.get("company_name") or "").strip().casefold(),
            str(row.get("job_title") or "").strip().casefold(),
            str(row.get("posted_at") or "").strip(),
        )
        if identity[0] and identity[1]:
            _export_rows.setdefault(identity, {
                "company_name": row.get("company_name") or "Unknown",
                "posted_at": row.get("posted_at") or "",
                "job_title": row.get("job_title") or "",
                "location": row.get("location") or "",
                "skills": row.get("skills") if isinstance(row.get("skills"), list) else [],
                "url": row.get("url") or "",
            })
            _seen_composite_keys.add(identity)
    return len(_export_rows)


async def _check_db() -> bool:
    """Try to connect to PostgreSQL once; cache the result."""
    global _db_available
    if _db_available is not None:
        return _db_available
    try:
        from app.database.session import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        _db_available = True
        log.info("✓ PostgreSQL connection verified")
    except Exception as exc:
        _db_available = False
        log.warning("✗ PostgreSQL unavailable (%s) — falling back to JSONL", exc)
    return _db_available


def _get_jsonl_path() -> Path:
    global _jsonl_path
    if _jsonl_path is None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        _jsonl_path = PROJECT_ROOT / "data" / "exports" / f"mass_scrape_{ts}.jsonl"
        _jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        log.info("JSONL fallback file: %s", _jsonl_path)
    return _jsonl_path


async def store_jobs(
    jobs: list[NormalizedJob],
    company_config: dict,
    progress: Progress,
    jsonl_only: bool = False,
) -> None:
    """Persist a batch of NormalizedJob records.  DB-first with JSONL fallback."""
    _capture_export_rows(jobs)
    if not jobs:
        return

    unique_jobs = []
    dupes = 0
    for job in jobs:
        key = _composite_key(job)
        if key in _seen_composite_keys:
            dupes += 1
            continue
        _seen_composite_keys.add(key)
        unique_jobs.append(job)
    if dupes:
        await progress.add(dupes=dupes)
    if not unique_jobs:
        return

    use_db = (not jsonl_only) and await _check_db()

    if use_db:
        await _store_db(unique_jobs, company_config, progress)
    else:
        await _store_jsonl(unique_jobs, progress)


async def _store_db(jobs: list[NormalizedJob], company_config: dict, progress: Progress):
    from app.database.session import SessionLocal
    from app.persistence.jobs import upsert_job

    stored = 0
    dupes = 0
    errs = 0
    async with SessionLocal() as session:
        for job in jobs:
            try:
                from sqlalchemy import func, select
                from app.database.models import Job
                existing_composite = await session.execute(
                    select(Job.id).where(
                        func.lower(Job.company_name) == (job.company_name or "").strip().lower(),
                        func.lower(Job.title) == (job.title or "").strip().lower(),
                        Job.posted_at.is_(None) if job.posted_at is None else Job.posted_at == job.posted_at,
                    ).limit(1)
                )
                if existing_composite.scalar_one_or_none() is not None:
                    dupes += 1
                    continue
                async with session.begin_nested():
                    outcome = await upsert_job(session, job, company_config, job.raw_data_path)
                if outcome == "inserted":
                    stored += 1
                elif outcome in {"unchanged", "updated"}:
                    dupes += 1
                elif outcome == "rejected":
                    errs += 1
            except Exception:
                errs += 1
        await session.commit()
    await progress.add(stored=stored, dupes=dupes, errs=errs)


_jsonl_lock = asyncio.Lock()
_seen_keys: set[str] = set()


async def _store_jsonl(jobs: list[NormalizedJob], progress: Progress):
    path = _get_jsonl_path()
    stored = 0
    dupes = 0
    async with _jsonl_lock:
        with open(path, "a", encoding="utf-8") as f:
            for job in jobs:
                key = "\x1f".join(_composite_key(job))
                if key in _seen_keys:
                    dupes += 1
                    continue
                _seen_keys.add(key)
                row = {
                    "title": job.title,
                    "company": job.company_name,
                    "location": job.location,
                    "technology_stack": job.skills,
                    "description": (job.description or "")[:2000],
                    "source_url": job.source_url or job.apply_url,
                    "date_posted": str(job.posted_at) if job.posted_at else None,
                    "source": job.source,
                    "source_job_id": job.source_job_id,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                stored += 1
    await progress.add(stored=stored, dupes=dupes)


# =====================================================================
# Save raw JSON responses to data/raw/
# =====================================================================

def save_raw(source: str, key: str, payload) -> str:
    day = datetime.now(UTC).date().isoformat()
    directory = PROJECT_ROOT / "data" / "raw" / day / source
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", key).strip("_")[:90] or "response"
    path = directory / f"{slug}_{uuid.uuid4().hex[:8]}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return str(path.relative_to(PROJECT_ROOT))


# =====================================================================
# Individual source scrapers
# =====================================================================

async def _scrape_board(
    collector_cls,
    company_config: dict,
    source_cfg: dict,
    sem: asyncio.Semaphore,
    progress: Progress,
    jsonl_only: bool,
):
    """Scrape a single company board (Greenhouse/Lever/Ashby) under semaphore."""
    source_name = collector_cls.source if hasattr(collector_cls, "source") else company_config.get("ats", "unknown")
    label = f"{source_name}/{company_config['name']}"
    collector = _make_collector(collector_cls)
    collector.request_interval = 0.3  # Faster for concurrent scraping
    fetch_ok = False
    try:
        async with sem:
            cfg = {**source_cfg, **company_config}
            raw_jobs = await collector.fetch(cfg)
            fetch_ok = True

        if not raw_jobs:
            log.debug("  %s — 0 jobs", label)
            return

        raw_path = save_raw(source_name, company_config["name"], raw_jobs)

        normalized: list[NormalizedJob] = []
        norm_errs = 0
        for raw in raw_jobs:
            try:
                job = enrich(collector.normalize(raw, cfg))
                enrich_classification(job)
                job.raw_data_path = raw_path
                if job.source_job_id and job.title and job.company_name:
                    normalized.append(job)
            except Exception:
                norm_errs += 1

        await progress.add(fetched=len(raw_jobs), errs=norm_errs)
        if normalized:
            await store_jobs(normalized, company_config, progress, jsonl_only)

        log.info("  %-45s  fetched=%d  normalized=%d", label, len(raw_jobs), len(normalized))

    except Exception as exc:
        await progress.add(errs=1)
        log.warning("  %-45s  ERROR: %s", label, exc)
    finally:
        state = "throttled" if collector.throttled else ("failed" if collector.failed or not fetch_ok else "exhausted")
        await progress.source_state(label, state, collector.retry_queue)
        await collector.close()
        await progress.source_done()


async def _scrape_aggregator(
    collector_cls,
    source_cfg: dict,
    sem: asyncio.Semaphore,
    progress: Progress,
    jsonl_only: bool,
):
    """Scrape a paginated aggregator (RemoteOK, Arbeitnow, Jobicy, etc.)."""
    name = collector_cls.source if hasattr(collector_cls, "source") else "aggregator"
    dummy_company = {
        "name": name.title(),
        "country": None,
        "region": "global",
        "ats": name,
        "ats_identifier": name,
        "enabled": True,
    }
    collector = _make_collector(collector_cls)
    collector.request_interval = 0.5
    fetch_ok = False
    try:
        async with sem:
            cfg = {**source_cfg, **dummy_company}
            raw_jobs = await collector.fetch(cfg)
            fetch_ok = True

        if not raw_jobs:
            log.info("  %-45s  0 jobs", name)
            return

        raw_path = save_raw(name, name, raw_jobs)

        normalized: list[NormalizedJob] = []
        norm_errs = 0
        for raw in raw_jobs:
            try:
                job = enrich(collector.normalize(raw, cfg))
                enrich_classification(job)
                job.raw_data_path = raw_path
                if job.source_job_id and job.title and job.company_name:
                    normalized.append(job)
            except Exception:
                norm_errs += 1

        await progress.add(fetched=len(raw_jobs), errs=norm_errs)
        if normalized:
            await store_jobs(normalized, dummy_company, progress, jsonl_only)

        log.info("  %-45s  fetched=%d  normalized=%d", name, len(raw_jobs), len(normalized))

    except Exception as exc:
        await progress.add(errs=1)
        log.warning("  %-45s  ERROR: %s", name, exc)
    finally:
        state = "throttled" if collector.throttled else ("failed" if collector.failed or not fetch_ok else "exhausted")
        await progress.source_state(name, state, collector.retry_queue)
        await collector.close()
        await progress.source_done()


# =====================================================================
# Build the full task list
# =====================================================================

def _build_tasks(
    sem: asyncio.Semaphore,
    progress: Progress,
    jsonl_only: bool,
    himalayas_only: bool = False,
) -> list:
    """Return a list of coroutines — one per source/company board."""
    import yaml
    sources_yml = PROJECT_ROOT / "config" / "sources.yml"
    settings = yaml.safe_load(sources_yml.read_text(encoding="utf-8")) if sources_yml.exists() else {"sources": {}}
    companies_yml = PROJECT_ROOT / "config" / "companies.yml"
    registry = yaml.safe_load(companies_yml.read_text(encoding="utf-8")) if companies_yml.exists() else []

    tasks: list = []

    if himalayas_only:
        source_cfg = settings.get("sources", {}).get("himalayas", {})
        source_cfg.setdefault("page_size", 20)
        tasks.append(_scrape_aggregator(HimalayasCollector, source_cfg, sem, progress, jsonl_only))
        return tasks

    # ── 1. Aggregator sources (no per-company config needed) ──
    aggregators = {
        "remoteok": (RemoteOKCollector, {}),
        "arbeitnow": (ArbeitnowCollector, {}),
        "jobicy": (JobicyCollector, {"count": 200}),
        "himalayas": (HimalayasCollector, {"page_size": 20}),
        "remotive": (RemotiveCollector, {}),
    }
    for name, (cls, defaults) in aggregators.items():
        cfg = {**defaults, **settings.get("sources", {}).get(name, {})}
        tasks.append(_scrape_aggregator(cls, cfg, sem, progress, jsonl_only))

    # ── 2. API-key aggregators (only if credentials present) ──
    if app_settings.adzuna_app_id and app_settings.adzuna_app_key:
        adzuna_cfg = settings.get("sources", {}).get("adzuna", {})
        adzuna_cfg.setdefault("countries", ["gb", "us", "de", "au", "ca", "in", "fr", "nl", "sg", "za"])
        adzuna_cfg.setdefault("results_per_page", 50)
        search_terms_yml = PROJECT_ROOT / "config" / "search_terms.yml"
        search_terms = {}
        if search_terms_yml.exists():
            search_terms = yaml.safe_load(search_terms_yml.read_text(encoding="utf-8")) or {}
        adzuna_cfg["keywords"] = adzuna_cfg.get("keywords") or [
            v for vals in search_terms.get("technology_search_terms", {}).values() for v in vals
        ]
        tasks.append(_scrape_aggregator(AdzunaCollector, adzuna_cfg, sem, progress, jsonl_only))

    if app_settings.usajobs_api_key and app_settings.usajobs_email:
        usajobs_cfg = settings.get("sources", {}).get("usajobs", {})
        usajobs_cfg.setdefault("results_per_page", 500)
        search_terms_yml = PROJECT_ROOT / "config" / "search_terms.yml"
        search_terms = {}
        if search_terms_yml.exists():
            search_terms = yaml.safe_load(search_terms_yml.read_text(encoding="utf-8")) or {}
        usajobs_cfg["keywords"] = usajobs_cfg.get("keywords") or [
            v for vals in search_terms.get("technology_search_terms", {}).values() for v in vals
        ]
        tasks.append(_scrape_aggregator(USAJobsCollector, usajobs_cfg, sem, progress, jsonl_only))

    if app_settings.jooble_api_key:
        jooble_cfg = settings.get("sources", {}).get("jooble", {})
        jooble_cfg.setdefault("results_per_page", 20)
        search_terms_yml = PROJECT_ROOT / "config" / "search_terms.yml"
        search_terms = {}
        if search_terms_yml.exists():
            search_terms = yaml.safe_load(search_terms_yml.read_text(encoding="utf-8")) or {}
        jooble_cfg["keywords"] = jooble_cfg.get("keywords") or [
            v for vals in search_terms.get("technology_search_terms", {}).values() for v in vals
        ]
        jooble_cfg.setdefault("countries", ["Kenya", "Nigeria", "South Africa", "Ghana", "United States", "United Kingdom", "Germany", "India"])
        tasks.append(_scrape_aggregator(JoobleCollector, jooble_cfg, sem, progress, jsonl_only))

    # ── 3. Per-company ATS boards from config/companies.yml ──
    for company in registry:
        if not company.get("enabled", True):
            continue
        ats = company.get("ats")
        cls_map = {"greenhouse": GreenhouseCollector, "lever": LeverCollector, "ashby": AshbyCollector}
        cls = cls_map.get(ats)
        if not cls:
            continue
        source_cfg = settings.get("sources", {}).get(ats, {})
        tasks.append(_scrape_board(cls, company, source_cfg, sem, progress, jsonl_only))

    # ── 4. Expanded Greenhouse boards ──
    gh_cfg = settings.get("sources", {}).get("greenhouse", {})
    for ident in EXTRA_GREENHOUSE:
        if ident in _EXISTING_GH:
            continue
        company = {
            "name": ident.replace("-", " ").title(),
            "ats": "greenhouse",
            "ats_identifier": ident,
            "enabled": True,
        }
        tasks.append(_scrape_board(GreenhouseCollector, company, gh_cfg, sem, progress, jsonl_only))

    # ── 5. Expanded Lever boards ──
    lever_cfg = settings.get("sources", {}).get("lever", {})
    for ident in EXTRA_LEVER:
        if ident in _EXISTING_LEVER:
            continue
        company = {
            "name": ident.replace("-", " ").title(),
            "ats": "lever",
            "ats_identifier": ident,
            "enabled": True,
        }
        tasks.append(_scrape_board(LeverCollector, company, lever_cfg, sem, progress, jsonl_only))

    # ── 6. Expanded Ashby boards ──
    ashby_cfg = settings.get("sources", {}).get("ashby", {})
    for ident in EXTRA_ASHBY:
        if ident in _EXISTING_ASHBY:
            continue
        company = {
            "name": ident.replace("-", " ").title(),
            "ats": "ashby",
            "ats_identifier": ident,
            "enabled": True,
        }
        tasks.append(_scrape_board(AshbyCollector, company, ashby_cfg, sem, progress, jsonl_only))

    return tasks


# =====================================================================
# Progress printer (runs as background task)
# =====================================================================

async def _progress_printer(progress: Progress, interval: float = 3.0):
    """Print live progress every `interval` seconds until all source tasks finish."""
    while progress.sources_done < progress.sources_total:
        print(f"\r{progress.line()}", end="", flush=True)
        await asyncio.sleep(interval)
    print(f"\r{progress.line()}")  # Final line


# =====================================================================
# Main entry point
# =====================================================================

def _parse_timestamp(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=UTC)
    elif isinstance(value, (int, float)):
        try:
            stamp = value / 1000 if abs(value) > 100_000_000_000 else value
            parsed = datetime.fromtimestamp(stamp, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.combine(date.fromisoformat(raw[:10]), datetime.min.time(), tzinfo=UTC)
            except ValueError:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _print_coverage(progress: Progress):
    dates = [dt for row in _export_rows.values() if (dt := _parse_timestamp(row.get("posted_at"))) is not None]
    if dates:
        oldest, newest = min(dates), max(dates)
        days = (newest - oldest).total_seconds() / 86400
        window = f"{days:.1f} days" if days % 1 else f"{int(days)} days"
        log.info("Oldest posting date: %s", oldest.isoformat())
        log.info("Newest posting date: %s", newest.isoformat())
        log.info("Total timeline window: Covering %s of job postings (%d dated records)", window, len(dates))
    else:
        log.info("Timeline dates: no valid posted_at timestamps found")
    log.info("Total unique postings: %s", len(_export_rows))
    exhausted = sum(1 for state in progress.source_states.values() if state == "exhausted")
    throttled = sum(1 for state in progress.source_states.values() if state == "throttled")
    failed = sum(1 for state in progress.source_states.values() if state == "failed")
    log.info("Sources exhausted: %d | throttled: %d | failed: %d", exhausted, throttled, failed)
    retry_path = PROJECT_ROOT / "retry_queue.json"
    retry_path.write_text(json.dumps(progress.retry_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if progress.retry_queue:
        log.info("Retry queue saved: %s (%d exhausted endpoint retries)", retry_path.name, len(progress.retry_queue))


async def run(workers: int = 20, jsonl_only: bool = False, *, himalayas_only: bool = False, resume_existing: bool = False):
    sem = asyncio.Semaphore(workers)
    progress = Progress()

    if resume_existing:
        resumed = _load_existing_export()
        progress.sources_done = 280
        progress.source_states.update({f"previously-exhausted-{i + 1}": "exhausted" for i in range(280)})
        log.info("Resuming with %s previously exported postings", resumed)

    tasks = _build_tasks(sem, progress, jsonl_only, himalayas_only=himalayas_only)
    progress.sources_total = len(tasks) + progress.sources_done

    log.info("=" * 72)
    log.info("MASS SCRAPE — exhaust all enabled pagination  |  %d workers  |  %d sources", workers, len(tasks))
    log.info("=" * 72)

    # Start the progress printer
    printer = asyncio.create_task(_progress_printer(progress, interval=2.0))

    # Fire all tasks; the semaphore gates concurrency
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Let the printer finish
    await printer

    export_error = None
    try:
        _write_exports()
        _print_coverage(progress)
    except Exception as exc:
        export_error = exc
        log.exception("Could not write consolidated CSV/JSON exports")

    # Summary
    exc_count = sum(1 for r in results if isinstance(r, Exception))
    print()
    log.info("=" * 72)
    log.info(
        "DONE  |  %d unique stored  |  %d fetched  |  %d duplicates  |  %d errors  |  %d task exceptions",
        progress.unique_stored,
        progress.total_fetched,
        progress.duplicates,
        progress.errors,
        exc_count,
    )
    log.info("Elapsed: %.1f seconds", time.monotonic() - progress._start)
    if export_error:
        raise RuntimeError("Failed to write full job postings exports") from export_error
    if _jsonl_path:
        log.info("JSONL output: %s", _jsonl_path)
    log.info("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Mass concurrent tech-job scraper")
    parser.add_argument("--workers", type=int, default=20, help="Max concurrent HTTP requests (default: 20)")
    parser.add_argument("--jsonl-only", action="store_true", help="Skip PostgreSQL, write to JSONL file only")
    parser.add_argument("--himalayas-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--resume-existing", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    asyncio.run(run(workers=args.workers, jsonl_only=args.jsonl_only,
                    himalayas_only=args.himalayas_only, resume_existing=args.resume_existing))


if __name__ == "__main__":
    main()
