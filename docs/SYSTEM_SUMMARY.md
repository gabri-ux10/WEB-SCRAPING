# System File Summary

This document maps the important files in TechJobs Aggregator and explains how a public job listing moves from a source endpoint into PostgreSQL, the API, and export files. It describes the checked-in system and the bulk-scrape snapshot generated on 2026-10-14.

## How a scrape works

### Standard application scrape

1. `python -m app.cli scrape` reads runtime settings and source/company configuration.
2. `app/services/scraping.py` selects enabled sources and coordinates their collectors.
3. A collector in `app/collectors/` requests public API or ATS pages through `app/collectors/base.py`, follows that source's pagination, and returns raw listing records.
4. The service saves raw payloads under `data/raw/`, maps source fields into `NormalizedJob`, normalizes and validates records, assigns categories and skills, then sends valid records to persistence.
5. `app/persistence/jobs.py` resolves source/company/location rows and inserts or updates jobs, skills, and history in PostgreSQL. A source ID plus source posting ID identifies a posting. Similar cross-source postings are recorded as candidates and are not automatically merged.
6. FastAPI exposes read-only search and status endpoints. The CLI can export database rows as CSV, JSON, or JSONL.

### Concurrent bulk scrape

`mass_scrape.py` builds tasks for enabled public feeds and configured ATS company boards, and limits concurrent asynchronous work with a semaphore. Its shared HTTP layer uses a 10-second request timeout, retries network/timeout/429/transient server errors three times with exponential backoff and jitter, and records terminal failures in `retry_queue.json`. Pagination stops when a source reports an empty page, 404, absent/repeated cursor, or a page with no new posting IDs. The bulk export uses `(company_name, job_title, posted_at)` for cross-source deduplication.

Bulk output files at the repository root:

| File | Contents |
|---|---|
| `job_postings_full.csv` | Consolidated records with `company_name`, `posted_at`, `job_title`, `location`, `skills`, and `url`; skills are semicolon-separated. |
| `job_postings_full.json` | Same records and fields; skills remain an array. |
| `retry_queue.json` | Source, last error, and attempt count for endpoints that failed the retry policy. |

The bulk runner buffers a source's fetched records before handing them to the persistence/export stage. This means a deep cursor feed can take a long time and its per-page progress is not shown by the top-level source counter. A terminal source failure may leave that source's records out of the final export; check `retry_queue.json` and the completion summary before treating all sources as exhausted.

## Repository map

### Root files

| File | Purpose |
|---|---|
| `mass_scrape.py` | Concurrent bulk runner, source task construction, deduplication, persistence/fallback, exports, and date/source summary. |
| `README.md` | Quick project overview, source list, setup, operations, and links to the longer guides. |
| `pyproject.toml` | Python package metadata, runtime/development dependencies, pytest settings, and Ruff configuration. |
| `Dockerfile` | Container image for the API application. |
| `docker-compose.yml` | Local PostgreSQL 16 and API services with a persistent database volume. |
| `Makefile` | Convenience targets for common local development commands. |
| `alembic.ini` | Alembic migration configuration. |
| `.gitignore` | Excludes local environments, secrets, caches, logs, and raw/regular export artifacts. |

### Application code (`app/`)

| Path | Purpose |
|---|---|
| `app/cli.py` | CLI entry point for scrape, database export, row count, and health check commands. |
| `app/config.py` | Environment and `.env` settings, including database URL, optional API credentials, request timeout, and retry defaults. |
| `app/schemas/job.py` | Pydantic job models shared by collectors and persistence. |
| `app/services/scraping.py` | Standard scrape orchestration, raw snapshot writes, validation/enrichment, persistence, run/error recording, and database exports. |
| `app/collectors/base.py` | Shared asynchronous HTTP client, timeout and retry handling, 404 exhaustion handling, and retry queue recording. |
| `app/collectors/greenhouse.py` | Public Greenhouse Job Board API connector. |
| `app/collectors/lever.py` | Public Lever Postings API connector. |
| `app/collectors/ashby.py` | Public Ashby job postings connector. |
| `app/collectors/aggregators.py` | Optional Adzuna and USAJOBS API connectors; credentials are required. |
| `app/collectors/arbeitnow.py` | Paginated public Arbeitnow connector. |
| `app/collectors/himalayas.py` | Cursor-paginated Himalayas remote-jobs connector. |
| `app/collectors/jobicy.py` | Public Jobicy remote-jobs connector. |
| `app/collectors/remoteok.py` | Remote OK public JSON feed connector. |
| `app/collectors/remotive.py` | Remotive remote-jobs connector with technology-category filtering. |
| `app/collectors/__init__.py` | Collector package marker. |
| `app/normalization/normalize.py` | Shared cleanup and normalization helpers. |
| `app/normalization/locations.py` | Location parsing and country/city hints. |
| `app/normalization/titles.py` | Job-title normalization. |
| `app/normalization/salaries.py` | Salary field and currency normalization helpers. |
| `app/classification/classifier.py` | Category assignment and skill-extraction orchestration. |
| `app/classification/categories.py` | Built-in category terms and category helpers. |
| `app/classification/skills.py` | Skill extraction rules and configured skills. |
| `app/deduplication/deduplicator.py` | Content hashing and similarity scoring for duplicate candidates. |
| `app/persistence/jobs.py` | PostgreSQL upsert logic for sources, companies, locations, jobs, skills, and history. Duplicate legacy location/company lookups use the first matching row. |
| `app/database/models.py` | SQLAlchemy table definitions and relationships. |
| `app/database/session.py` | Asynchronous SQLAlchemy engine and session factory. |
| `app/api/main.py` | FastAPI application setup and router registration. |
| `app/api/routes/jobs.py` | Read-only job listing, filtering, and single-job routes. |
| `app/api/routes/companies.py` | Read-only company routes. |
| `app/api/routes/sources.py` | Source listing and statistics routes. |

### Configuration (`config/`)

| File | Purpose |
|---|---|
| `config/sources.yml` | Source enablement, request parameters, paging, and source-specific behavior. |
| `config/companies.yml` | ATS board identifiers and company metadata. |
| `config/regions.yml` | Named regional groupings used by scrape filters. |
| `config/search_terms.yml` | Technology-related search phrases for API aggregators. |
| `config/tech_categories.yml` | Editable technology categories and matching terms. |
| `config/skills.yml` | Configurable skill vocabulary. |

### Database, docs, and verification

| Path | Purpose |
|---|---|
| `migrations/env.py` | Alembic environment connected to application settings. |
| `migrations/versions/0001_initial.py` | Initial PostgreSQL schema migration. |
| `migrations/script.py.mako` | Template for generated migration revisions. |
| `docs/PROJECT_GUIDE.md` | Setup, configuration, operations, API, and deployment guide. |
| `docs/SYSTEM_SUMMARY.md` | This repository and data-flow summary. |
| `tests/test_api.py` | API route tests. |
| `tests/test_collectors.py` | Collector behavior tests. |
| `tests/test_deduplication.py` | Deduplication and similarity tests. |
| `tests/test_normalization.py` | Normalization tests. |
| `tests/test_persistence.py` | Database persistence tests. |

## Configuration and data locations

- `.env` holds local secrets and runtime values such as `DATABASE_URL`; it is ignored by Git. Start from `.env.example` in a fresh clone.
- `data/raw/YYYY-MM-DD/<source>/` stores uniquely named raw source snapshots for the standard application scrape.
- `data/exports/` is the default destination for `app.cli export` outputs.
- The bulk runner writes the three root-level files listed above.
- PostgreSQL stores normalized job, company, source, location, skill, scrape-run, error, history, and duplicate-candidate records. Alembic applies schema changes.

## Snapshot and limits (2026-10-14)

- Consolidated CSV rows: **26,148**.
- Consolidated JSON rows: **26,148**; counts and field sets match the CSV.
- PostgreSQL rows in `jobs`: **31,018** at verification time.
- Every export composite key was found in PostgreSQL after import and timestamp normalization.
- Export posting dates span **2009-12-05** through **2026-10-14** (about **6,157.4 days**).
- The earlier pass completed 280 source tasks. The resumed Himalayas request failed with a connection error after three attempts. It is listed in `retry_queue.json`; therefore the Himalayas feed was not confirmed exhausted and the exports should not be described as a complete snapshot of that feed.
