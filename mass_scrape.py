#!/usr/bin/env python3
"""
mass_scrape.py — High-throughput concurrent tech-job scraper.

Fires all configured sources + expanded company boards in parallel via asyncio,
persists into PostgreSQL (dedup by source+source_job_id unique constraint),
falls back to JSONL when the database is unavailable, and prints real-time
progress to the terminal.

Usage:
    python mass_scrape.py                     # full run, target 30 000 unique jobs
    python mass_scrape.py --target 5000       # stop after 5 000 unique jobs
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
from datetime import UTC, datetime
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
    def __init__(self, target: int):
        self.target = target
        self.total_fetched = 0
        self.unique_stored = 0
        self.duplicates = 0
        self.errors = 0
        self.sources_done = 0
        self.sources_total = 0
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

    def hit_target(self) -> bool:
        return self.unique_stored >= self.target

    def line(self) -> str:
        elapsed = time.monotonic() - self._start
        rate = self.unique_stored / elapsed if elapsed > 0 else 0
        return (
            f"[+] Stored {self.unique_stored:,}/{self.target:,} unique  |  "
            f"fetched {self.total_fetched:,}  |  dupes {self.duplicates:,}  |  "
            f"errs {self.errors:,}  |  sources {self.sources_done}/{self.sources_total}  |  "
            f"{rate:.0f} jobs/s  |  {elapsed:.0f}s"
        )


# =====================================================================
# Database helpers
# =====================================================================

_db_available: bool | None = None
_jsonl_path: Path | None = None
EXPORT_FIELDS = ["company_name", "posted_at", "job_title", "location", "skills", "url", "source"]
_export_rows: dict[str, dict] = {}


def _capture_export_rows(jobs: list[NormalizedJob]) -> None:
    """Keep one normalized row per canonical source URL (or source ID fallback)."""
    from urllib.parse import urlsplit, urlunsplit

    for job in jobs:
        url = job.source_url or job.apply_url or ""
        if url:
            parts = urlsplit(url)
            identity = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
        else:
            identity = f"{job.source}::{job.source_job_id}"
        if not identity:
            continue
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
                "source": job.source,
            },
        )


def _write_exports() -> tuple[Path, Path, int]:
    """Write the consolidated run dataset to JSON and CSV using the same field set."""
    records = list(_export_rows.values())
    json_path = PROJECT_ROOT / "job_postings.json"
    csv_path = PROJECT_ROOT / "job_postings.csv"
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
    if not jobs or progress.hit_target():
        return

    use_db = (not jsonl_only) and await _check_db()

    if use_db:
        await _store_db(jobs, company_config, progress)
    else:
        await _store_jsonl(jobs, progress)


async def _store_db(jobs: list[NormalizedJob], company_config: dict, progress: Progress):
    from app.database.session import SessionLocal
    from app.persistence.jobs import upsert_job

    stored = 0
    dupes = 0
    errs = 0
    async with SessionLocal() as session:
        for job in jobs:
            if progress.hit_target():
                break
            try:
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
                if progress.hit_target():
                    break
                key = f"{job.source}::{job.source_job_id}"
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
    try:
        async with sem:
            if progress.hit_target():
                return
            cfg = {
                **source_cfg,
                **company_config,
                "max_pages": source_cfg.get("max_pages", 10),
                "max_jobs": source_cfg.get("max_jobs", 10000),
            }
            raw_jobs = await collector.fetch(cfg)

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
    try:
        async with sem:
            if progress.hit_target():
                return
            cfg = {
                **source_cfg,
                **dummy_company,
                "max_pages": source_cfg.get("max_pages", 20),
                "max_jobs": source_cfg.get("max_jobs", 10000),
            }
            raw_jobs = await collector.fetch(cfg)

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
        await collector.close()
        await progress.source_done()


# =====================================================================
# Build the full task list
# =====================================================================

def _build_tasks(
    sem: asyncio.Semaphore,
    progress: Progress,
    jsonl_only: bool,
) -> list:
    """Return a list of coroutines — one per source/company board."""
    import yaml
    sources_yml = PROJECT_ROOT / "config" / "sources.yml"
    settings = yaml.safe_load(sources_yml.read_text(encoding="utf-8")) if sources_yml.exists() else {"sources": {}}
    companies_yml = PROJECT_ROOT / "config" / "companies.yml"
    registry = yaml.safe_load(companies_yml.read_text(encoding="utf-8")) if companies_yml.exists() else []

    tasks: list = []

    # ── 1. Aggregator sources (no per-company config needed) ──
    aggregators = {
        "remoteok": (RemoteOKCollector, {"max_jobs": 5000}),
        "arbeitnow": (ArbeitnowCollector, {"max_pages": 10, "max_jobs": 5000}),
        "jobicy": (JobicyCollector, {"max_pages": 20, "count": 200, "max_jobs": 5000}),
        # Himalayas permits public cursor pagination (20/page); keep a bounded daily walk.
        "himalayas": (HimalayasCollector, {"max_pages": 10, "page_size": 20, "max_jobs": 200}),
        # Remotive advises at most four public API requests per day; fetch its feed once.
        "remotive": (RemotiveCollector, {"max_jobs": 5000}),
    }
    for name, (cls, defaults) in aggregators.items():
        cfg = {**defaults, **settings.get("sources", {}).get(name, {})}
        tasks.append(_scrape_aggregator(cls, cfg, sem, progress, jsonl_only))

    # ── 2. API-key aggregators (only if credentials present) ──
    if app_settings.adzuna_app_id and app_settings.adzuna_app_key:
        adzuna_cfg = settings.get("sources", {}).get("adzuna", {})
        adzuna_cfg.setdefault("countries", ["gb", "us", "de", "au", "ca", "in", "fr", "nl", "sg", "za"])
        adzuna_cfg.setdefault("max_pages", 5)
        adzuna_cfg.setdefault("results_per_page", 50)
        adzuna_cfg.setdefault("max_jobs", 10000)
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
        usajobs_cfg.setdefault("max_pages", 10)
        usajobs_cfg.setdefault("results_per_page", 100)
        usajobs_cfg.setdefault("max_jobs", 5000)
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
        jooble_cfg.setdefault("max_requests_per_run", 20)
        jooble_cfg.setdefault("max_jobs", 5000)
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
    """Print live progress every `interval` seconds until target is hit."""
    while not progress.hit_target() and progress.sources_done < progress.sources_total:
        print(f"\r{progress.line()}", end="", flush=True)
        await asyncio.sleep(interval)
    print(f"\r{progress.line()}")  # Final line


# =====================================================================
# Main entry point
# =====================================================================

async def run(target: int = 30_000, workers: int = 20, jsonl_only: bool = False):
    sem = asyncio.Semaphore(workers)
    progress = Progress(target)

    tasks = _build_tasks(sem, progress, jsonl_only)
    progress.sources_total = len(tasks)

    log.info("=" * 72)
    log.info("MASS SCRAPE — target=%d unique jobs  |  %d workers  |  %d sources", target, workers, len(tasks))
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
        raise RuntimeError("Failed to write job_postings.csv/job_postings.json") from export_error
    if _jsonl_path:
        log.info("JSONL output: %s", _jsonl_path)
    log.info("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Mass concurrent tech-job scraper")
    parser.add_argument("--target", type=int, default=30_000, help="Stop after this many unique jobs (default: 30000)")
    parser.add_argument("--workers", type=int, default=20, help="Max concurrent HTTP requests (default: 20)")
    parser.add_argument("--jsonl-only", action="store_true", help="Skip PostgreSQL, write to JSONL file only")
    args = parser.parse_args()

    asyncio.run(run(target=args.target, workers=args.workers, jsonl_only=args.jsonl_only))


if __name__ == "__main__":
    main()
