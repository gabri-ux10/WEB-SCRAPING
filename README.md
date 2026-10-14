# TechJobs Aggregator

An ingestion-focused Python service for collecting publicly listed technology jobs through public ATS endpoints and optional job APIs. Connectors are isolated from the pipeline; raw JSON snapshots are saved before normalization. The API and exports preserve source and application links.

See the [project and deployment guide](docs/PROJECT_GUIDE.md) for setup and deployment, and the [system file summary](docs/SYSTEM_SUMMARY.md) for a file-by-file map of the repository and a description of how data moves through it.

## Architecture

`FETCH → SAVE RAW → NORMALIZE → VALIDATE → CLASSIFY → EXTRACT SKILLS → DEDUPLICATE → UPSERT → HISTORY`

`app/collectors/` contains independent connectors. `app/services/scraping.py` coordinates them and records run/error rows. SQLAlchemy models are in `app/database/models.py`; Alembic owns schema changes. API routes are read-only. No browser automation or private job APIs are used.

## Supported sources

| Source | Connector | Default | Access |
|---|---|---:|---|
| Greenhouse | public Job Board API | enabled | per-company public board token |
| Lever | public Postings API | enabled | per-company public site name |
| Ashby | public Job Postings API | enabled | per-company public job-board name |
| Adzuna | Search API | disabled | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` |
| USAJOBS | official Search API | disabled | `USAJOBS_API_KEY`, `USAJOBS_EMAIL` |
| Jooble | regional REST API | disabled | regional key; finite lifetime request allowance |
| Jobicy | public remote jobs API | enabled | public endpoint; canonical Jobicy listing URL retained |
| Remote OK | public JSON feed | enabled | public endpoint; source listing URL retained |
| Arbeitnow | public job-board API | enabled | paginated public endpoint |
| Himalayas | public remote-jobs API | enabled | cursor pagination; 20 jobs per request |
| Remotive | public remote-jobs API | enabled | one request per run; tech categories only |

Greenhouse uses `boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`. Lever reads published postings from `/v0/postings/{site}?mode=json`. Ashby reads its public job-board endpoint and filters unlisted postings. The public Ashby response does not expose a stable posting ID, so the connector uses `jobUrl` as the deterministic identity fallback.

Source documentation: [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [Ashby public Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api), [Adzuna Search](https://developer.adzuna.com/docs/search), [USAJOBS Search](https://developer.usajobs.gov/api-reference/get-api-search), [Jooble REST API](https://help.jooble.org/en/support/solutions/articles/60001448238-rest-api-documentation), [Jobicy API](https://jobicy.com/jobs-rss-feed).

Remote OK exposes a free public JSON feed at `https://remoteok.com/api`. Arbeitnow provides a paginated public job-board API. Himalayas supports cursor-based pagination with up to 20 jobs per page and recommends avoiding frequent polling. Remotive's public API returns active remote listings; this scraper requests it once per run, filters to technology-related categories, and retains its attribution source and original listing URL.

Source documentation: [Remote OK public feed](https://remoteok.com/faq), [Arbeitnow API](https://documenter.getpostman.com/view/18545278/UVJbJdKh), [Himalayas Remote Jobs API](https://himalayas.app/docs/remote-jobs-api), [Remotive Remote Jobs API](https://github.com/remotive-com/remote-jobs-api).

## Install and run

Requires Python 3.12+, Docker Compose, and a Python virtual environment for the local CLI.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d
alembic upgrade head
python -m app.cli scrape
```

Or use `make install`, `make up`, `make migrate`, and `make scrape` where GNU Make is installed. PostgreSQL binds only to host loopback (`127.0.0.1:5432`). The API container listens on `http://localhost:8000`.

The host CLI uses `localhost:5432`; Compose's app container uses the internal `db` hostname. Leave the `.env` database URL at localhost for host-side CLI use.

## Credentials

Copy `.env.example` to `.env`, then add credentials only for connectors you enable. Never commit `.env`. Adzuna requires app ID/key. USAJOBS requires the assigned API key and a contact email in the documented User-Agent. Jooble keys are tied to regional domains and the free tier has a finite lifetime request allowance; configure an approved regional domain and keep `max_requests_per_run` small. Missing credentials skip that optional connector without interrupting ATS collection.

## Add a company

Edit `config/companies.yml`. Find its official career page, identify the ATS from the public page URL or company-provided information, then verify the exact board token/site name using the provider's public endpoint. Do not guess. Example:

```yaml
- name: My Startup
  country: KE
  region: kenya
  website: https://example.invalid
  careers_url: https://example.invalid/careers
  ats: ashby
  ats_identifier: verified-public-job-board-name
  enabled: true
```

The checked-in company entries are configured for their named public ATS boards. Verify identifiers against the company's current careers page before adding or changing entries; do not guess board identifiers.

## Scraping

```powershell
python -m app.cli scrape
python -m app.cli scrape --source greenhouse
python -m app.cli scrape --country KE
python -m app.cli scrape --region africa
python -m app.cli scrape --company "My Startup"
python -m app.cli scrape --dry-run --max-pages 1 --max-jobs 50
```

Source options live in `config/sources.yml`; country groups are in `config/regions.yml`; aggregator search keywords are in `config/search_terms.yml`; categories and skill terms are editable in `config/tech_categories.yml` and `config/skills.yml`. Raw snapshots use unique names under `data/raw/YYYY-MM-DD/<source>/`; snapshots are never overwritten. Run/error rows retain per-company outcomes.

For a concurrent bulk run across the configured public feeds and company boards, use:

```powershell
python mass_scrape.py --workers 20
```

`mass_scrape.py` uses asynchronous concurrency, a 10-second HTTP timeout, and pagination until feeds report exhaustion or are marked failed. It writes `job_postings_full.csv` and `job_postings_full.json` in the repository root. Both files contain `company_name`, `posted_at`, `job_title`, `location`, `skills`, and `url`; `skills` is a list in JSON and semicolon-separated in CSV. Records are deduplicated by `(company_name, job_title, posted_at)`. The completion report includes date coverage and source outcomes; endpoints that still fail after three retries are recorded in `retry_queue.json`. PostgreSQL is used when available, with JSONL as a persistence fallback.

The verified snapshot generated on 2026-10-14 contains 26,148 unique export records. All 26,148 composite keys were verified in PostgreSQL (31,018 total job rows at verification time). In this run, 280 source tasks had completed in the earlier pass; the resumed Himalayas feed failed after three connection attempts and is recorded in `retry_queue.json`, so that feed was not fully exhausted.

## API

Start Compose and open `http://localhost:8000/docs`.

```text
GET /health
GET /jobs?country=KE&category=Software%20Engineering&remote_type=remote
GET /jobs?region=africa
GET /jobs?q=python&skill=Python&limit=25&offset=0
GET /jobs/{id}
GET /companies
GET /companies/{id}
GET /sources
GET /stats
```

Jobs filters include `q`, `country`, `region`, `city`, `remote_type`, `employment_type`, `category`, `skill`, `company`, `source`, `posted_after`, `posted_before`, and `salary_min`. Responses include source attribution fields, raw snapshot path, normalized location, categories, extracted skills, and source-specific metadata where provided.

## Export

```powershell
python -m app.cli export --format csv
python -m app.cli export --format json
python -m app.cli export --format jsonl --output data/exports/review.jsonl
```

Default output paths for the database export command are `data/exports/jobs.csv`, `jobs.json`, and `jobs.jsonl`. The standalone `mass_scrape.py` bulk command writes the root-level `job_postings_full.csv` and `job_postings_full.json` files described above, plus `retry_queue.json` when endpoints fail after retries.

## Database schema

Tables: `sources`, `companies`, `locations`, `jobs`, `job_history`, `skills`, `job_skills`, `scrape_runs`, `scrape_errors`, and `duplicate_candidates`. `(source_id, source_job_id)` is unique. Meaningful content changes save previous state before updating. Jobs missing from a fully successful company feed accrue missing observations and are closed after the configured threshold; failed or malformed company runs never advance missing counts. Cross-source matches are candidates with scores; matches are never merged automatically. Run migrations with `alembic upgrade head`; inspect autogenerate output before applying schema changes.

## Compliance and scheduling

Only public postings are requested. The project does not bypass authentication, CAPTCHA, access restrictions, or bot protections. Use verified public board identifiers, respect provider terms and quotas, and disable connectors that are not approved for your use. Requests have timeouts and retry transient connection, timeout, 429, and 5xx failures with exponential backoff. Jobicy, Remotive, and Himalayas source attribution and original listing URLs are preserved. Salary currencies are not converted.

Example six-hour schedule: `0 */6 * * * python -m app.cli scrape`. Configure its working directory, Python environment and log destination.

## Tests and troubleshooting

```powershell
pytest
ruff check app tests
```

If the database is unavailable, check `docker compose ps` and run `python -m app.cli health`. If a company returns 404, verify its ATS identifier. If an optional connector reports absent credentials, provide the required variables and enable that source. Partial scrape errors appear in the CLI summary, application logs and `scrape_errors` table.

## MVP limits and roadmap

- Company entries are placeholders until their public identifiers are verified.
- Geographic coverage depends on curated public company identifiers and enabled aggregator APIs.
- Cross-source candidate matching is conservative and has no automatic merge workflow.
- Adzuna returns abbreviated job descriptions in its search response.
- Future work: operations metrics, source-specific quota controls, structured compensation parsing, and durable pagination checkpoints.
