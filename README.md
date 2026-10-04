# TechJobs Aggregator

An ingestion-focused Python service for collecting publicly listed technology jobs through public ATS endpoints and optional job APIs. Connectors are isolated from the pipeline; raw JSON snapshots are saved before normalization. The API and exports preserve source and application links.

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
| Jooble | regional REST API | disabled | regional key; request cap enforced |
| Jobicy | public remote jobs API | disabled | public endpoint; canonical Jobicy listing URL retained |

Greenhouse uses `boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`. Lever reads published postings from `/v0/postings/{site}?mode=json`. Ashby reads its public job-board endpoint and filters unlisted postings. The public Ashby response does not expose a stable posting ID, so the connector uses `jobUrl` as the deterministic identity fallback.

Source documentation: [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [Ashby public Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api), [Adzuna Search](https://developer.adzuna.com/docs/search), [USAJOBS Search](https://developer.usajobs.gov/api-reference/get-api-search), [Jooble REST API](https://help.jooble.org/en/support/solutions/articles/60001448238-rest-api-documentation), [Jobicy API](https://jobicy.com/jobs-rss-feed).

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

The checked-in entries are disabled placeholders and are not assertions that those companies use the named ATS products. Keep unverified entries disabled until you confirm the identifier.

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

Default output paths are `data/exports/jobs.csv`, `jobs.json`, and `jobs.jsonl`.

## Database schema

Tables: `sources`, `companies`, `locations`, `jobs`, `job_history`, `skills`, `job_skills`, `scrape_runs`, `scrape_errors`, and `duplicate_candidates`. `(source_id, source_job_id)` is unique. Meaningful content changes save previous state before updating. Jobs missing from a fully successful company feed accrue missing observations and are closed after the configured threshold; failed or malformed company runs never advance missing counts. Cross-source matches are candidates with scores; matches are never merged automatically. Run migrations with `alembic upgrade head`; inspect autogenerate output before applying schema changes.

## Compliance and scheduling

Only public postings are requested. The project does not bypass authentication, CAPTCHA, access restrictions, or bot protections. Use verified public board identifiers, respect provider terms and quotas, and disable connectors that are not approved for your use. Requests have timeouts and retry transient connection, timeout, 429, and 5xx failures with exponential backoff. Jobicy attribution and canonical source URL are preserved. Salary currencies are not converted.

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
